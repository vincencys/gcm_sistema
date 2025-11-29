from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.views import LoginView
from django.conf import settings
import base64
import uuid
from .models import Perfil
from .forms import GcmPerfilForm, RegistrarUsuarioForm
import os
from io import BytesIO
from django.http import HttpResponseForbidden

@login_required
def perfil(request):
    perfil, _ = Perfil.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = GcmPerfilForm(request.POST, request.FILES, instance=perfil)
        if form.is_valid():
            # Processar assinatura digital se fornecida
            assinatura_digital = form.cleaned_data.get('assinatura_digital')
            assinatura_tipo = form.cleaned_data.get('assinatura_tipo')
            
            if assinatura_tipo == 'digital' and assinatura_digital:
                # Converter base64 para arquivo
                try:
                    format, imgstr = assinatura_digital.split(';base64,')
                    ext = format.split('/')[-1]
                    data = ContentFile(base64.b64decode(imgstr), name=f'assinatura_digital_{uuid.uuid4().hex[:8]}.{ext}')
                    
                    # Limpar assinatura upload se usando digital
                    form.instance.assinatura_img = data
                except Exception as e:
                    messages.error(request, f"Erro ao processar assinatura digital: {e}")
                    
            elif assinatura_tipo == 'upload':
                # Limpar assinatura digital se usando upload
                form.instance.assinatura_digital = ''
            
            form.save()
            messages.success(request, "Perfil atualizado com sucesso.")
            return redirect("users:perfil")
    else:
        form = GcmPerfilForm(instance=perfil)
        # Definir tipo inicial baseado nos dados existentes
        if perfil.assinatura_digital:
            form.fields['assinatura_tipo'].initial = 'digital'
        elif perfil.assinatura_img:
            form.fields['assinatura_tipo'].initial = 'upload'
            
    return render(request, "users/perfil.html", {"form": form, "perfil": perfil})

def registrar(request):
    if request.method == "POST":
        form = RegistrarUsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário criado. Faça login para continuar.")
            return redirect("users:login")
    else:
        form = RegistrarUsuarioForm()
    return render(request, "users/registrar.html", {"form": form})


@login_required
def twofa_configurar(request):
    """Gera/mostra segredo TOTP e QR para o usuário configurar 2FA."""
    user = request.user
    # guardar segredo em session para demo; ideal: campo no modelo user/perfil
    # imports lazy para não quebrar o servidor se libs não instaladas
    try:
        import pyotp  # type: ignore
        import qrcode  # type: ignore
    except Exception:
        messages.error(request, '2FA indisponível: instale os pacotes pyotp e qrcode.')
        return render(request, 'users/2fa_configurar.html', {'secret': None, 'qr_b64': None})

    secret = request.session.get('2fa_secret')
    if not secret:
        secret = pyotp.random_base32()
        request.session['2fa_secret'] = secret
    issuer = 'Sistema GCM'
    otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.username, issuer_name=issuer)
    # gerar QR base64
    buf = BytesIO()
    try:
        img = qrcode.make(otp_uri)
        img.save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode()
    finally:
        buf.close()
    return render(request, 'users/2fa_configurar.html', {'secret': secret, 'qr_b64': qr_b64})


@login_required
def twofa_validar(request):
    """Valida o código TOTP e marca sessão como 2FA verificada."""
    if request.method == 'POST':
        try:
            import pyotp  # type: ignore
        except Exception:
            messages.error(request, '2FA indisponível: instale o pacote pyotp.')
            return render(request, 'users/2fa_validar.html')
        code = (request.POST.get('code') or '').strip().replace(' ', '')
        secret = request.session.get('2fa_secret')
        if not secret:
            messages.error(request, '2FA não configurado para esta sessão.')
            return redirect('users:twofa_configurar')
        totp = pyotp.TOTP(secret)
        if totp.verify(code, valid_window=1):
            request.session['2fa_ok'] = True
            messages.success(request, '2FA verificado com sucesso.')
            return redirect('core:dashboard')
        messages.error(request, 'Código inválido. Tente novamente.')
    return render(request, 'users/2fa_validar.html')


class RememberLoginView(LoginView):
    """Login que respeita o checkbox 'Lembrar-me'.

    - Marcado: sessão persiste pelo período de SESSION_COOKIE_AGE (padrão: 2 semanas).
    - Desmarcado: sessão expira ao fechar o navegador (set_expiry(0)).
    """

    def form_valid(self, form):
        response = super().form_valid(form)
        remember = (self.request.POST.get('remember') or '').lower() in {'1', 'true', 'on', 'yes'}
        if remember:
            # Usa o tempo padrão configurado
            age = getattr(settings, 'SESSION_COOKIE_AGE', 1209600)
            self.request.session.set_expiry(age)
        else:
            # Expira ao fechar o navegador
            self.request.session.set_expiry(0)
        return response

    def form_invalid(self, form):
        # Mostra um aviso claro quando as credenciais estiverem incorretas
        messages.error(self.request, 'Usuário ou senha inválidos')
        return super().form_invalid(form)


def password_reset_request(request):
    """
    Recebe um identificador (usuário ou e-mail de recuperação) e envia um link de
    redefinição de senha para o e-mail de recuperação do perfil (fallback: user.email).
    A resposta é sempre de sucesso por segurança, independente de encontrar usuário.
    """
    if request.method == 'POST':
        ident = (request.POST.get('identificador') or '').strip()
        user = None
        if ident:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            # 1) tentar por username
            try:
                user = User.objects.select_related('perfil').get(username__iexact=ident)
            except User.DoesNotExist:
                user = None
            # 2) tentar por matrícula (perfil.matricula)
            if user is None:
                try:
                    pf = Perfil.objects.select_related('user').get(matricula__iexact=ident)
                    user = pf.user
                except Perfil.DoesNotExist:
                    user = None
            # 3) tentar por e-mail de recuperação
            if user is None:
                try:
                    pf = Perfil.objects.select_related('user').get(recovery_email__iexact=ident)
                    user = pf.user
                except Perfil.DoesNotExist:
                    user = None

        if user is not None and user.is_active:
            # e-mail de destino
            perfil = getattr(user, 'perfil', None)
            email_to = None
            if perfil and getattr(perfil, 'recovery_email', None):
                email_to = perfil.recovery_email
            elif getattr(user, 'email', None):
                email_to = user.email

            if email_to:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = request.build_absolute_uri(
                    reverse('users:password_reset_confirm', args=[uid, token])
                )
                subject = 'Redefinição de senha - Sistema GCM'
                text = (
                    'Olá,\n\n'
                    'Recebemos uma solicitação para redefinir sua senha no Sistema GCM.\n'
                    f'Use o link abaixo para criar uma nova senha (válido por tempo limitado):\n{reset_url}\n\n'
                    'Se você não solicitou, pode ignorar este e-mail.\n'
                )
                html = (
                    '<p>Olá,</p>'
                    '<p>Recebemos uma solicitação para redefinir sua senha no <b>Sistema GCM</b>.</p>'
                    f'<p>Use o link abaixo para criar uma nova senha (válido por tempo limitado):<br>'
                    f'<a href="{reset_url}" target="_blank">Redefinir senha</a></p>'
                    '<p>Se você não solicitou, pode ignorar este e-mail.</p>'
                )
                msg = EmailMultiAlternatives(subject, text, to=[email_to])
                msg.attach_alternative(html, 'text/html')
                try:
                    msg.send(fail_silently=False)
                except Exception as e:
                    # Log simples para diagnóstico em ambiente de dev/integração
                    try:
                        from django.utils.log import getLogger
                        getLogger(__name__).exception("Falha ao enviar e-mail de reset: %s", e)
                    except Exception:
                        print("[password_reset_request] Erro ao enviar e-mail:", e)

        # Sempre redireciona para a tela de "enviado" (não revela existência de usuário)
        return redirect('users:password_reset_done')

    return render(request, 'users/password_reset.html')

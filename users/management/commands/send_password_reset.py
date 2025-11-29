from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from users.models import Perfil


class Command(BaseCommand):
    help = "Envia e imprime um link de redefinição de senha para um usuário, usando recovery_email do Perfil (fallback: user.email)."

    def add_arguments(self, parser):
        parser.add_argument('--ident', required=True, help='username, matrícula (perfil) ou e-mail de recuperação')
        parser.add_argument('--host', default='localhost:8000', help='Host para montar URL (ex.: 192.168.1.7:8000)')
        parser.add_argument('--scheme', default='http', choices=['http', 'https'])

    def handle(self, *args, **opts):
        ident = opts['ident']
        host = opts['host']
        scheme = opts['scheme']

        User = get_user_model()
        user = None

        # 1) Por username
        try:
            user = User.objects.select_related('perfil').get(username__iexact=ident)
        except User.DoesNotExist:
            user = None

        # 2) Por matrícula
        if user is None:
            try:
                pf = Perfil.objects.select_related('user').get(matricula__iexact=ident)
                user = pf.user
            except Perfil.DoesNotExist:
                user = None

        # 3) Por recovery_email
        if user is None:
            try:
                pf = Perfil.objects.select_related('user').get(recovery_email__iexact=ident)
                user = pf.user
            except Perfil.DoesNotExist:
                user = None

        if user is None:
            raise CommandError('Nenhum usuário encontrado com o identificador informado.')

        perfil = getattr(user, 'perfil', None)
        email_to = (perfil.recovery_email if perfil and perfil.recovery_email else None) or getattr(user, 'email', None)
        if not email_to:
            raise CommandError('Usuário não possui recovery_email nem user.email definido.')

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        path = reverse('users:password_reset_confirm', args=[uid, token])
        reset_url = f"{scheme}://{host}{path}"

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
            f'<p><a href="{reset_url}">Redefinir senha</a></p>'
            '<p>Se você não solicitou, pode ignorar este e-mail.</p>'
        )

        self.stdout.write(f"→ Enviando para: {email_to}")
        self.stdout.write(f"→ Link: {reset_url}")

        msg = EmailMultiAlternatives(subject, text, to=[email_to])
        msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=False)

        self.stdout.write(self.style.SUCCESS('E-mail de redefinição enviado com sucesso.'))

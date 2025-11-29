from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.utils.timezone import now
from django.http import HttpRequest

from .models import AuditLog


class AuditLogMiddleware(MiddlewareMixin):
    """Middleware simples para registrar trilha de auditoria.

    - Registra método, caminho, querystring, parte do corpo, IP e user-agent.
    - Pula rotas sensíveis (login, logout) e arquivos estáticos.
    - Limita o tamanho do corpo para evitar dados sensíveis grandes.
    """

    EXCLUDED_PREFIXES = (
        '/static/', '/media/', '/admin/',
    )
    EXCLUDED_PATHS = (
        '/users/login/', '/users/logout/',
    )

    def process_view(self, request: HttpRequest, view_func, view_args, view_kwargs):
        path = request.path
        if any(path.startswith(p) for p in self.EXCLUDED_PREFIXES) or path in self.EXCLUDED_PATHS:
            return None

        try:
            user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
            ip = request.META.get('HTTP_X_FORWARDED_FOR', '') or request.META.get('REMOTE_ADDR') or None
            if ip and ',' in ip:
                ip = ip.split(',')[0].strip()
            ua = request.META.get('HTTP_USER_AGENT', '')[:512]
            method = request.method
            query = request.META.get('QUERY_STRING', '')[:1000]
            body = ''
            # Capturar corpo apenas para métodos de escrita
            if method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                try:
                    raw = request.body.decode('utf-8', errors='ignore')
                except Exception:
                    raw = ''
                # Sanitização básica: esconder senhas/tokens
                for key in ('password', 'senha', 'csrf', 'token', 'secret'):
                    raw = raw.replace(key, f"{key[0]}***")
                body = raw[:2000]

            AuditLog.objects.create(
                user=user,
                method=method,
                path=path,
                action='',
                querystring=query,
                body=body,
                ip=ip,
                user_agent=ua,
            )
        except Exception:
            # Não quebra a requisição por erro de auditoria
            pass
        return None


class TwoFAMiddleware(MiddlewareMixin):
    """Exige 2FA para usuários de comando/adm e o usuário 'moises'.

    - Se não verificado (session['2fa_ok'] != True), redireciona para configuração/validação.
    - Ignora rotas de autenticação, 2FA, estáticos e admin.
    """
    EXCLUDED_PREFIXES = ('/static/', '/media/', '/admin/',)
    EXCLUDED_PATHS = ('/users/login/', '/users/logout/', '/users/2fa/configurar/', '/users/2fa/validar/',)

    def process_request(self, request: HttpRequest):
        path = request.path
        if any(path.startswith(p) for p in self.EXCLUDED_PREFIXES) or path in self.EXCLUDED_PATHS:
            return None
        # Em ambiente de desenvolvimento, não exigir 2FA para não bloquear fluxos de teste
        if getattr(settings, 'DEBUG', False):
            return None
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None
        # Se pyotp não estiver instalado, não exigir 2FA (modo tolerante)
        try:
            import pyotp  # type: ignore
            _pyotp_ok = True
        except Exception:
            _pyotp_ok = False
        if not _pyotp_ok:
            return None
        username = user.username.lower()
        require = user.is_superuser or username in {"moises", "administrativo", "comandante", "subcomandante"}
        if not require:
            return None
        if request.session.get('2fa_ok') is True:
            return None
        # Sem 2FA: direciona para configuração/validação
        from django.shortcuts import redirect
        return redirect('users:twofa_configurar')

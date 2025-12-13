"""Sinais para registrar eventos de autenticação no Log Simplificado."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from common.audit_simple import record


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Registra login bem-sucedido no Log Simplificado."""
    try:
        record(
            request,
            event='LOGIN',
            message=f'Usuário {user.username} fez login',
            app='users',
        )
    except Exception:
        pass  # Não quebrar o fluxo de login por erro de log


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Registra logout no Log Simplificado."""
    try:
        if user:
            record(
                request,
                event='LOGOUT',
                message=f'Usuário {user.username} fez logout',
                app='users',
            )
    except Exception:
        pass


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    """Registra tentativa de login falha no Log Simplificado."""
    try:
        username = credentials.get('username', 'desconhecido')
        record(
            request,
            event='LOGIN_FAILED',
            message=f'Tentativa de login falha para: {username}',
            app='users',
        )
    except Exception:
        pass

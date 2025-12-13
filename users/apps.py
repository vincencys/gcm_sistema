from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'users'

    def ready(self):
        """Importar sinais quando o app estiver pronto."""
        try:
            import users.signals  # noqa: F401
        except Exception:
            pass

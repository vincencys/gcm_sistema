from django.apps import AppConfig

class TaloesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "taloes"
    verbose_name = "Talões"

    def ready(self):
        # Carrega os signals do app (atualização de KM das viaturas, etc.)
        from . import signals  # noqa: F401

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail, get_connection
from django.conf import settings


class Command(BaseCommand):
    help = "Envia um e-mail de teste usando a configuração SMTP atual."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            dest="to",
            help="E-mail de destino (ex.: seuemail@dominio.com)",
            required=True,
        )

    def handle(self, *args, **options):
        to_email = options.get("to")
        if not to_email:
            raise CommandError("Informe o destino com --to seuemail@dominio.com")

        subject = "[GCM Sistema] Teste de E-mail"
        body = (
            "Este é um e-mail de teste do GCM Sistema.\n\n"
            f"Backend: {settings.EMAIL_BACKEND}\n"
            f"Host: {getattr(settings, 'EMAIL_HOST', '')}:{getattr(settings, 'EMAIL_PORT', '')}\n"
            f"TLS: {getattr(settings, 'EMAIL_USE_TLS', False)} | SSL: {getattr(settings, 'EMAIL_USE_SSL', False)}\n"
            f"Remetente (DEFAULT_FROM_EMAIL): {getattr(settings, 'DEFAULT_FROM_EMAIL', '')}\n"
        )

        try:
            # Abre conexão explícita para falhas de auth ficarem claras
            with get_connection(
                backend=settings.EMAIL_BACKEND,
                host=getattr(settings, "EMAIL_HOST", None),
                port=getattr(settings, "EMAIL_PORT", None),
                username=getattr(settings, "EMAIL_HOST_USER", None),
                password=getattr(settings, "EMAIL_HOST_PASSWORD", None),
                use_tls=getattr(settings, "EMAIL_USE_TLS", False),
                use_ssl=getattr(settings, "EMAIL_USE_SSL", False),
                timeout=getattr(settings, "EMAIL_TIMEOUT", 15),
            ) as connection:
                sent = send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [to_email],
                    connection=connection,
                    fail_silently=False,
                )
        except Exception as exc:
            raise CommandError(f"Falha ao enviar e-mail: {exc}")

        if sent:
            self.stdout.write(self.style.SUCCESS(f"E-mail de teste enviado para {to_email}."))
        else:
            raise CommandError("Nenhum e-mail foi enviado (sent=0). Verifique as configurações.")

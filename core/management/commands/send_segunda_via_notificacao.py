from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory
from django.conf import settings
from django.urls import resolve

from core.models import NotificacaoFiscalizacao
from core.views import _enviar_segunda_via_notificacao


class Command(BaseCommand):
    help = "Envia a 'segunda via' de uma Notificação por e-mail com marca 'Via do Notificado'."

    def add_arguments(self, parser):
        parser.add_argument("--pk", type=int, help="ID da Notificação (se omitido, usa a mais recente)")
        parser.add_argument("--to", type=str, help="E-mail de destino (override opcional)")

    def handle(self, *args, **opts):
        pk = opts.get("pk")
        to = opts.get("to")

        n = None
        if pk:
            try:
                n = NotificacaoFiscalizacao.objects.get(pk=pk)
            except NotificacaoFiscalizacao.DoesNotExist:
                raise CommandError(f"Notificação pk={pk} não encontrada.")
        else:
            n = NotificacaoFiscalizacao.objects.order_by("-id").first()
            if not n:
                raise CommandError("Nenhuma Notificação encontrada na base.")

        # Monta uma request fictícia para construir URLs absolutas dentro do helper
        rf = RequestFactory()
        req = rf.get("/")
        host = None
        try:
            hosts = getattr(settings, "ALLOWED_HOSTS", []) or []
            if hosts and hosts[0] not in ("*",):
                host = hosts[0]
        except Exception:
            pass
        if not host:
            host = getattr(settings, "SITE_DOMAIN", None) or "localhost:8000"
        req.META["HTTP_HOST"] = host

        ok, err = _enviar_segunda_via_notificacao(req, n, via_do_notificado=True, destinatario_override=to)
        if ok:
            self.stdout.write(self.style.SUCCESS(
                f"Segunda via enviada para {to or n.notificado_email} (Notificação {n.numero})."
            ))
        else:
            raise CommandError(f"Falha no envio: {err}")

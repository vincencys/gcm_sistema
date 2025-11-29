# viaturas/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
import json

class Viatura(models.Model):
    class Status(models.TextChoices):
        EM_FUNCIONAMENTO = "FUNC", _("Em funcionamento")
        EM_MANUTENCAO   = "MANU", _("Em manutenção")
        BAIXADA         = "BAIX", _("Baixada (sem previsão)")

    prefixo = models.CharField("Prefixo", max_length=20, unique=True, db_index=True)
    placa = models.CharField("Placa", max_length=10, blank=True, null=True)

    status = models.CharField(
        "Status", max_length=4, choices=Status.choices,
        default=Status.EM_FUNCIONAMENTO, db_index=True
    )

    km_atual = models.PositiveIntegerField("KM atual", default=0)
    km_prox_troca_oleo = models.PositiveIntegerField(
        "Próxima troca de óleo (KM)", blank=True, null=True
    )
    km_prox_revisao = models.PositiveIntegerField(
        "Próxima revisão (KM)", blank=True, null=True
    )

    observacoes = models.TextField("Observações", blank=True)
    ativo = models.BooleanField("Ativa", default=True)  # “remover” = arquivar

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("prefixo",)
        verbose_name = "Viatura"
        verbose_name_plural = "Viaturas"

    def __str__(self):
        return self.prefixo

    # Helpers para UI
    @property
    def badge_css(self):
        return {
            self.Status.EM_FUNCIONAMENTO: "badge-success",
            self.Status.EM_MANUTENCAO: "badge-warning",
            self.Status.BAIXADA: "badge",
        }.get(self.status, "badge")

    @property
    def pendente_troca_oleo(self):
        return self.km_prox_troca_oleo is not None and self.km_atual >= self.km_prox_troca_oleo

    @property
    def pendente_revisao(self):
        return self.km_prox_revisao is not None and self.km_atual >= self.km_prox_revisao


class ViaturaAvariaEstado(models.Model):
    """Estado persistente de avarias em aberto por viatura.

    - É atualizado quando um checklist é salvo (união do dia) e quando avarias são resolvidas.
    - Serve como fonte para exibição imediata ao iniciar plantão, sem depender de checklist do dia.
    """
    viatura = models.OneToOneField(
        Viatura,
        on_delete=models.CASCADE,
        related_name="avarias_estado",
    )
    labels_json = models.TextField(blank=True, default="[]")  # lista de labels
    atualizado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Estado de Avarias da Viatura"
        verbose_name_plural = "Estados de Avarias das Viaturas"

    def set_labels(self, labels: list[str] | set[str]):
        uniq = sorted(set([str(x) for x in (labels or [])]))
        self.labels_json = json.dumps(uniq, ensure_ascii=False)
        self.atualizado_em = timezone.now()

    def get_labels(self) -> list[str]:
        try:
            return json.loads(self.labels_json or "[]")
        except Exception:
            return []


class AvariaResolvidaLog(models.Model):
    """Registro de resolução de avarias independente de plantão.

    Guarda quem resolveu, quando e quais labels foram marcadas como resolvidas.
    """
    viatura = models.ForeignKey(
        Viatura,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avarias_resolvidas_logs",
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    itens_json = models.TextField(blank=True, default="[]")
    criado_em = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-criado_em",)
        verbose_name = "Resolução de Avaria"
        verbose_name_plural = "Resoluções de Avarias"

    def itens(self):
        try:
            return json.loads(self.itens_json or "[]")
        except Exception:
            return []

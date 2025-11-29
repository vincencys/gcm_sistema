from django.db import models
from common.models import TimeStamped

# Modelos existentes (mantidos para compatibilidade)
class Dispositivo(TimeStamped):
    codigo = models.CharField(max_length=60, unique=True)
    vitima_nome = models.CharField(max_length=120)
    ativo = models.BooleanField(default=True)
    def __str__(self):
        return self.codigo

class Evento(TimeStamped):
    dispositivo = models.ForeignKey(Dispositivo, on_delete=models.PROTECT)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    prioridade = models.CharField(max_length=10, default='ALTA')
    status = models.CharField(
        max_length=16,
        default='ABERTO',
        choices=[('ABERTO','ABERTO'),('ATENDIMENTO','EM_ATENDIMENTO'),('ENCERRADO','ENCERRADO')]
    )
    despachado_para = models.ForeignKey('viaturas.Viatura', null=True, blank=True, on_delete=models.SET_NULL)


# Novos modelos para o fluxo completo do Botão do Pânico
class Assistida(TimeStamped):
    nome = models.CharField(max_length=120)
    cpf = models.CharField(max_length=14, unique=True)
    telefone = models.CharField(max_length=20)
    processo_mp = models.CharField(max_length=60)
    endereco = models.CharField(max_length=255)
    documento_mp = models.FileField(upload_to="mp_docs/")
    status = models.CharField(
        max_length=20,
        choices=[
            ("PENDENTE_VALIDACAO", "Pendente"),
            ("APROVADO", "Aprovado"),
            ("REPROVADO", "Reprovado"),
            ("SUSPENSO", "Suspenso"),
        ],
        default="PENDENTE_VALIDACAO",
    )
    token_panico = models.CharField(max_length=6, blank=True, null=True, unique=True)
    observacao_validacao = models.TextField(blank=True, null=True)

    def gerar_token(self, rotativo: bool = False):
        import secrets
        import string
        # Gera token de 6 caracteres alfanuméricos (letras maiúsculas e números)
        chars = string.ascii_uppercase + string.digits
        self.token_panico = ''.join(secrets.choice(chars) for _ in range(6))
        self.save(update_fields=["token_panico"])  # rotativo tratado em regras de negócio externas

    def __str__(self) -> str:
        return f"{self.nome} ({self.cpf})"


class DisparoPanico(TimeStamped):
    assistida = models.ForeignKey(Assistida, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20,
        choices=[
            ("ABERTA", "Aberta"),
            ("EM_ATENDIMENTO", "Em atendimento"),
            ("ENCERRADA", "Encerrada"),
            ("CANCELADA", "Cancelada"),
            ("FALSO_POSITIVO", "Falso positivo"),
            ("TESTE", "Teste"),
        ],
        default="ABERTA",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    precisao_m = models.IntegerField(null=True, blank=True)
    origem = models.CharField(max_length=20, default="APP")
    origem_ip = models.GenericIPAddressField(null=True, blank=True)
    origem_user_agent = models.CharField(max_length=512, blank=True)
    midia = models.FileField(upload_to="panico_midia/", blank=True, null=True)
    assumido_por = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    em_atendimento_em = models.DateTimeField(null=True, blank=True)
    encerrado_em = models.DateTimeField(null=True, blank=True)
    relato_final = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["assistida"]),
            models.Index(fields=["created_at"]),
        ]

    def marcar_atendimento(self, user):
        from django.utils import timezone
        if self.status == "ABERTA":
            self.status = "EM_ATENDIMENTO"
            self.assumido_por = user
            self.em_atendimento_em = timezone.now()
            self.save()

    def encerrar(self, relato: str, status_final: str = "ENCERRADA"):
        from django.utils import timezone
        self.status = status_final
        self.relato_final = relato
        self.encerrado_em = timezone.now()
        self.save()
        # Broadcast da mudança de status
        from .broadcast import broadcast_panico_status_mudou
        broadcast_panico_status_mudou(self)

    def __str__(self) -> str:
        return f"Pânico #{self.id} - {self.assistida.nome} - {self.status}"

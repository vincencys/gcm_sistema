from django.db import models
from django.conf import settings
import os
from django.utils import timezone
from django.contrib.auth import get_user_model


def escala_upload_path(instance, filename):
    base, ext = os.path.splitext(filename)
    ext = ext or ''
    return f"escala_mensal/{instance.ano}/{instance.mes:02d}/{base}{ext}"


class EscalaMensal(models.Model):
    ano = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField(help_text="1=Jan ... 12=Dez")
    arquivo = models.FileField(upload_to=escala_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("ano", "mes")
        ordering = ["-ano", "-mes"]

    def __str__(self) -> str:
        return f"Escala {self.mes:02d}/{self.ano}"


def audiencias_upload_path(instance, filename):
    base, ext = os.path.splitext(filename)
    ext = ext or ''
    return f"audiencias/{base}{ext}"


class Audiencias(models.Model):
    """Documento único de Audiências (apenas um registro ativo)."""
    arquivo = models.FileField(upload_to=audiencias_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Audiências"

    def __str__(self) -> str:
        return f"Audiências ({self.updated_at:%d/%m/%Y %H:%M})" if self.updated_at else "Audiências"


def ordem_servico_upload_path(instance, filename):
    base, ext = os.path.splitext(filename)
    ext = ext or ''
    return f"ordem_servico/{instance.ano}/{instance.mes:02d}/{base}{ext}"


class OrdemServico(models.Model):
    ano = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField(help_text="1=Jan ... 12=Dez")
    arquivo = models.FileField(upload_to=ordem_servico_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ano", "-mes", "-updated_at", "-created_at"]

    def __str__(self) -> str:
        return f"OS {self.mes:02d}/{self.ano} - {os.path.basename(self.arquivo.name)}"


def oficio_diverso_upload_path(instance, filename):
    base, ext = os.path.splitext(filename)
    ext = ext or ''
    return f"oficio_diverso/{instance.ano}/{instance.mes:02d}/{base}{ext}"


class OficioDiverso(models.Model):
    ano = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField(help_text="1=Jan ... 12=Dez")
    arquivo = models.FileField(upload_to=oficio_diverso_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ano", "-mes", "-updated_at", "-created_at"]

    def __str__(self) -> str:
        return f"Ofício Diverso {self.mes:02d}/{self.ano} - {os.path.basename(self.arquivo.name)}"


class Dispensa(models.Model):
    PLANTAO_CHOICES = (
        ("A", "Plantão A"),
        ("B", "Plantão B"),
        ("C", "Plantão C"),
        ("D", "Plantão D"),
    )
    TIPO_CHOICES = (
        ("LEI", "Dispensa de Lei"),
        ("BANCO", "Banco de Horas"),
        ("TROCA", "Troca de Serviço"),
    )
    TURNO_CHOICES = (
        ("DIURNO", "Diurno"),
        ("NOTURNO", "Noturno"),
    )
    STATUS_CHOICES = (
        ("PENDENTE", "Pendente de aprovação"),
        ("APROVADA", "Aprovada"),
        ("RECUSADA", "Recusada"),
        ("CANCELADA", "Cancelada"),
    )

    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dispensas_solicitadas")
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dispensas_para_aprovar")
    plantao = models.CharField(max_length=1, choices=PLANTAO_CHOICES)
    data = models.DateField()
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    turno = models.CharField(max_length=8, choices=TURNO_CHOICES, default="DIURNO")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDENTE")
    mensagem_recusa = models.TextField(blank=True)
    observacao = models.TextField(blank=True)
    aprovado_em = models.DateTimeField(null=True, blank=True)
    recusado_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    cancelado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dispensas_canceladas")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-created_at"]
        constraints = [
            # Permite nova solicitação no mesmo dia quando a anterior foi CANCELADA
            models.UniqueConstraint(
                fields=["solicitante", "data", "turno"],
                condition=models.Q(status__in=["PENDENTE","APROVADA","RECUSADA"]),
                name="uniq_dispensa_dia_turno_usuario_nao_cancelada",
            ),
            models.CheckConstraint(check=models.Q(plantao__in=["A","B","C","D"]), name="disp_plantao_valido"),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} - {self.data:%d/%m/%Y} ({self.get_status_display()})"


# --------------------- Fiscalização: Notificações ---------------------
def notificacao_assinatura_upload(instance, filename):
    base, ext = os.path.splitext(filename)
    ext = ext or '.png'
    ano = instance.emissao_em.year if instance.emissao_em else timezone.now().year
    return f"notificacoes/assinaturas/{ano}/{instance.numero or 'novo'}{ext}"


class NotificacaoFiscalizacao(models.Model):
    """Registro de Notificação (Fiscalização).

    Campos principais segundo layout fornecido pelo usuário.
    """
    numero = models.CharField(max_length=32, unique=True, blank=True)
    emissao_em = models.DateTimeField(auto_now_add=True)

    # Dados do notificado
    notificado_nome = models.CharField(max_length=200)
    notificado_email = models.EmailField(blank=True)
    notificado_cpf = models.CharField(max_length=14, blank=True)  # armazenar apenas dígitos (até 11) ou formatado
    notificado_cnpj = models.CharField(max_length=18, blank=True) # armazenar apenas dígitos (até 14) ou formatado
    endereco = models.CharField(max_length=200, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    atividade_ramo = models.CharField(max_length=160, blank=True)

    # Conteúdo
    referente = models.TextField(blank=True)
    prazo_dias = models.PositiveIntegerField(null=True, blank=True)
    prazo_horas = models.PositiveIntegerField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    # Assinaturas/Registros
    data_recebimento = models.DateField(null=True, blank=True)
    compareceu_em = models.DateField(null=True, blank=True)
    fiscal_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='notificacoes_fiscal')
    fiscal_matricula = models.CharField(max_length=30, blank=True)

    # Assinatura do notificado
    recusou_assinar = models.BooleanField(default=False)
    assinatura_notificado = models.ImageField(upload_to=notificacao_assinatura_upload, null=True, blank=True)

    # Verificação (QR/Token)
    validacao_token = models.CharField(max_length=64, blank=True)
    validacao_hash = models.CharField(max_length=64, blank=True)

    # Status de despacho
    STATUS_CHOICES = (
        ("AGUARDANDO", "Aguardando despacho"),
        ("DESPACHADO", "Despachado"),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="AGUARDANDO", db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-emissao_em', '-created_at']

    def __str__(self) -> str:
        return f"Notificação {self.numero or 'sem-numero'} - {self.notificado_nome}"

    def gerar_numero(self):
        """Gera número no formato NOT-YYYY-#### sequencial por ano."""
        ano = (self.emissao_em or timezone.now()).year
        prefix = f"NOT-{ano}"
        ultimo = (
            NotificacaoFiscalizacao.objects
            .filter(numero__startswith=f"{prefix}-")
            .order_by('-numero')
            .first()
        )
        seq = 1
        if ultimo and '-' in ultimo.numero:
            try:
                seq = int(ultimo.numero.split('-')[-1]) + 1
            except Exception:
                seq = 1
        return f"{prefix}-{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.numero:
            # Gera número único
            for _ in range(5):
                num = self.gerar_numero()
                if not NotificacaoFiscalizacao.objects.filter(numero=num).exists():
                    self.numero = num
                    break
        super().save(*args, **kwargs)


# --------------------- Fiscalização: Autos de Infração ---------------------
def auto_com_assinatura_upload(instance, filename):
    base, ext = os.path.splitext(filename)
    ext = ext or '.png'
    ano = instance.emissao_em.year if instance.emissao_em else timezone.now().year
    return f"autos/comercio/assinaturas/{ano}/{instance.numero or 'novo'}{ext}"


def auto_som_assinatura_upload(instance, filename):
    base, ext = os.path.splitext(filename)
    ext = ext or '.png'
    ano = instance.emissao_em.year if instance.emissao_em else timezone.now().year
    return f"autos/som/assinaturas/{ano}/{instance.numero or 'novo'}{ext}"


class AutoInfracaoComercio(models.Model):
    """Auto de Infração (Comércios).

    Mantém mesma experiência da Notificação: lista, formulário com assinatura
    e envio de segunda via por e-mail. Os campos específicos foram reduzidos
    ao essencial conforme layout enviado.
    """
    numero = models.CharField(max_length=32, unique=True, blank=True)
    emissao_em = models.DateTimeField(auto_now_add=True)

    # Notificado
    notificado_nome = models.CharField(max_length=200)
    notificado_email = models.EmailField(blank=True)
    notificado_cpf = models.CharField(max_length=14, blank=True)
    notificado_cnpj = models.CharField(max_length=18, blank=True)
    endereco = models.CharField(max_length=200, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado_civil = models.CharField(max_length=40, blank=True)
    profissao_atividade = models.CharField(max_length=160, blank=True)
    inscricao_municipal = models.CharField(max_length=60, blank=True)

    # Infração / dispositivos legais
    descricao_infracao = models.TextField(blank=True)
    artigos_infringidos = models.CharField(max_length=160, blank=True)
    lei_numero = models.CharField(max_length=80, blank=True)
    lei_data = models.DateField(null=True, blank=True)
    valor_multa = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    ENTREGA_CHOICES = (
        ("PES", "Entregue pessoalmente"),
        ("POS", "Via postal"),
    )
    notificacao_entrega = models.CharField(max_length=3, choices=ENTREGA_CHOICES, blank=True)
    prazo_defesa_dias = models.PositiveIntegerField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    # Fiscal
    fiscal_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='autos_comercio_fiscal')
    fiscal_matricula = models.CharField(max_length=30, blank=True)

    # Assinatura do autuado
    recusou_assinar = models.BooleanField(default=False)
    assinatura_notificado = models.ImageField(upload_to=auto_com_assinatura_upload, null=True, blank=True)

    # Verificação (QR/Token)
    validacao_token = models.CharField(max_length=64, blank=True)
    validacao_hash = models.CharField(max_length=64, blank=True)

    # Status de despacho
    STATUS_CHOICES = (
        ("AGUARDANDO", "Aguardando despacho"),
        ("DESPACHADO", "Despachado"),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="AGUARDANDO", db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-emissao_em', '-created_at']

    def __str__(self) -> str:
        return f"Auto Comércio {self.numero or 'sem-numero'} - {self.notificado_nome}"

    def gerar_numero(self):
        ano = (self.emissao_em or timezone.now()).year
        prefix = f"AIC-{ano}"
        ultimo = (
            AutoInfracaoComercio.objects
            .filter(numero__startswith=f"{prefix}-")
            .order_by('-numero')
            .first()
        )
        seq = 1
        if ultimo and '-' in ultimo.numero:
            try:
                seq = int(ultimo.numero.split('-')[-1]) + 1
            except Exception:
                seq = 1
        return f"{prefix}-{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.numero:
            for _ in range(5):
                num = self.gerar_numero()
                if not AutoInfracaoComercio.objects.filter(numero=num).exists():
                    self.numero = num
                    break
        super().save(*args, **kwargs)


class AutoInfracaoSom(models.Model):
    """Auto de Infração Ambiental / Poluição Sonora."""
    numero = models.CharField(max_length=32, unique=True, blank=True)
    emissao_em = models.DateTimeField(auto_now_add=True)

    # Notificado / Identificação
    notificado_nome = models.CharField(max_length=200)
    notificado_email = models.EmailField(blank=True)
    notificado_cpf = models.CharField(max_length=14, blank=True)
    notificado_cnpj = models.CharField(max_length=18, blank=True)
    endereco = models.CharField(max_length=200, blank=True)
    referencia = models.CharField(max_length=160, blank=True)
    ponto = models.CharField(max_length=80, blank=True)

    # Medição
    valor_medido_db = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    permitido_db = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    PERIODO_CHOICES = (
        ("DIURNO", "Diurno (7h–19h)"),
        ("VESPERTINO", "Vespertino (19h–22h)"),
        ("NOTURNO", "Noturno (22h–7h)"),
    )
    periodo = models.CharField(max_length=10, choices=PERIODO_CHOICES, blank=True)

    # Reincidência
    RECID_CHOICES = (
        ("0", "Não"),
        ("1", "1ª"),
        ("2", "2ª"),
        ("3", "3ª"),
        ("10", "10ª"),
    )
    reincidencia = models.CharField(max_length=3, choices=RECID_CHOICES, default="0")

    base_legal = models.TextField(blank=True)
    CLASS_CHOICES = (
        ("LEVE", "Leve"),
        ("GRAVE", "Grave"),
        ("GRAVISSIMA", "Gravíssima"),
    )
    classificacao = models.CharField(max_length=12, choices=CLASS_CHOICES, blank=True)
    observacoes = models.TextField(blank=True)

    # Fiscal
    fiscal_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='autos_som_fiscal')
    fiscal_matricula = models.CharField(max_length=30, blank=True)

    # Assinatura (infrator)
    recusou_assinar = models.BooleanField(default=False)
    assinatura_notificado = models.ImageField(upload_to=auto_som_assinatura_upload, null=True, blank=True)

    # Verificação (QR/Token)
    validacao_token = models.CharField(max_length=64, blank=True)
    validacao_hash = models.CharField(max_length=64, blank=True)

    # Status de despacho
    STATUS_CHOICES = (
        ("AGUARDANDO", "Aguardando despacho"),
        ("DESPACHADO", "Despachado"),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="AGUARDANDO", db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-emissao_em', '-created_at']

    def __str__(self) -> str:
        return f"Auto Som {self.numero or 'sem-numero'} - {self.notificado_nome}"

    def gerar_numero(self):
        ano = (self.emissao_em or timezone.now()).year
        prefix = f"AIS-{ano}"
        ultimo = (
            AutoInfracaoSom.objects
            .filter(numero__startswith=f"{prefix}-")
            .order_by('-numero')
            .first()
        )
        seq = 1
        if ultimo and '-' in ultimo.numero:
            try:
                seq = int(ultimo.numero.split('-')[-1]) + 1
            except Exception:
                seq = 1
        return f"{prefix}-{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.numero:
            for _ in range(5):
                num = self.gerar_numero()
                if not AutoInfracaoSom.objects.filter(numero=num).exists():
                    self.numero = num
                    break
        super().save(*args, **kwargs)


# --------------------- Administração: Ofício Interno ---------------------
class OficioInterno(models.Model):
    """Documento simples de Ofício Interno com fluxo de decisão.

    Fluxo:
    - Criado pelo usuário (criador) para um supervisor escolhido.
    - Status inicial: PEND_SUP (Pendente do Supervisor) e responsável atual = supervisor.
    - Supervisor pode: Deferir, Indeferir, ou Despachar para SUBCMT/CMT.
    - Se despachado: responsável atual passa a ser o respectivo usuário (subcomandante/comandante).
    - Sub/CMT podem Deferir/Indeferir.
    """

    TIPO_CHOICES = (
        ("INFO", "Informação"),
        ("SOL", "Solicitação"),
        ("JUS", "Justificativa"),
        ("SUG", "Sugestão"),
        ("CRI", "Crítica"),
    )

    STATUS_CHOICES = (
        ("PEND_SUP", "Pendente do Supervisor"),
        ("PEND_SUB", "Pendente do Subcomandante"),
        ("PEND_CMT", "Pendente do Comandante"),
        ("DEFERIDO", "Deferido"),
        ("INDEFERIDO", "Indeferido"),
    )

    criador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="oficios_criados")
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="oficios_supervisor")
    responsavel_atual = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="oficios_pendentes", null=True, blank=True)
    tipo = models.CharField(max_length=4, choices=TIPO_CHOICES)
    texto = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="PEND_SUP", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"Ofício #{self.id} - {self.get_tipo_display()} ({self.get_status_display()})"


class OficioAcao(models.Model):
    """Histórico de decisões/andamentos do Ofício Interno."""

    ACOES = (
        ("CRIAR", "Criar"),
        ("DEFERIR", "Deferir"),
        ("INDEFERIR", "Indeferir"),
        ("DESP_SUB", "Despachar para SUBCMT"),
        ("DESP_CMT", "Despachar para CMT"),
    )

    oficio = models.ForeignKey(OficioInterno, on_delete=models.CASCADE, related_name="acoes")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="oficios_acoes")
    acao = models.CharField(max_length=10, choices=ACOES)
    observacao = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


# --------------------- Notificações do Usuário (Centro de Notificações) ---------------------
class UserNotification(models.Model):
    """Notificação simples e persistente para um usuário.

    Ex.: BO devolvido para correção, avisos do sistema, etc.
    """
    KIND_CHOICES = (
        ("BO_RECUSA", "BO devolvido para correção"),
        ("SISTEMA", "Aviso do sistema"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_notifications")
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default="SISTEMA")
    title = models.CharField(max_length=160)
    message = models.TextField(blank=True)
    link_url = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.get_kind_display()} -> {getattr(self.user,'username','?')}"

    @property
    def is_unread(self) -> bool:
        return self.read_at is None

    def mark_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            try:
                self.save(update_fields=["read_at"])  # pragma: no cover
            except Exception:
                pass


# --------------------- Banco de Horas ---------------------
User = get_user_model()

class BancoHorasSaldo(models.Model):
    """Saldo consolidado do Banco de Horas por usuário (em minutos).

    Um registro por usuário. Atualizado via lançamentos.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='banco_horas_saldo')
    saldo_minutos = models.IntegerField(default=0, help_text="Saldo em minutos (positivo=crédito, negativo=débito)")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Saldo de Banco de Horas"
        verbose_name_plural = "Saldos de Banco de Horas"

    def __str__(self) -> str:  # pragma: no cover
        return f"{getattr(self.user,'username','?')}: {self.saldo_minutos} min"


class BancoHorasLancamento(models.Model):
    """Lançamentos do Banco de Horas (razão/ledger).

    minutos: valor assinado (positivo adiciona, negativo remove).
    origem: MANUAL | LIVRO_CECOM | DISPENSA
    ref_type/ref_id: referência livre ao objeto origem (opcional).
    """
    ORIGEM_CHOICES = (
        ("MANUAL", "Ajuste Manual"),
        ("LIVRO_CECOM", "Livro CECOM"),
        ("DISPENSA", "Dispensa - Banco de Horas"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='banco_horas_lancamentos')
    minutos = models.IntegerField(help_text="Valor em minutos. Positivo adiciona, negativo subtrai.")
    origem = models.CharField(max_length=16, choices=ORIGEM_CHOICES, default="MANUAL")
    motivo = models.CharField(max_length=200, blank=True)
    ref_type = models.CharField(max_length=40, blank=True)
    ref_id = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user_id} {self.minutos:+d} min ({self.origem})"

    @staticmethod
    def ajustar_saldo(user: User, minutos: int, *, origem: str = "MANUAL", motivo: str = "", ref_type: str = "", ref_id: str = "", created_by: User | None = None) -> "BancoHorasLancamento":
        """Cria lançamento e atualiza o saldo do usuário de forma atômica simples."""
        if not user or not getattr(user, 'id', None):
            raise ValueError("Usuário inválido para ajuste de banco de horas")
        # cria/garante saldo
        saldo_obj, _ = BancoHorasSaldo.objects.get_or_create(user=user)
        # cria lançamento
        lanc = BancoHorasLancamento.objects.create(
            user=user,
            minutos=int(minutos or 0),
            origem=origem or "MANUAL",
            motivo=motivo or "",
            ref_type=ref_type or "",
            ref_id=str(ref_id or ""),
            created_by=created_by,
        )
        # atualiza saldo
        saldo_obj.saldo_minutos = (saldo_obj.saldo_minutos or 0) + int(minutos or 0)
        saldo_obj.save(update_fields=["saldo_minutos", "updated_at"])
        return lanc


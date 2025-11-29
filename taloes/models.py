from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


# =========================
#   Códigos de Ocorrência
# =========================

class GrupoOcorrencia(models.Model):
    """
    Grupo de códigos de ocorrência.
    (Substitui a ideia antiga de 'codigo'/'titulo'.)
    """
    nome = models.CharField("Nome do grupo", max_length=100, default="")
    descricao = models.CharField("Descrição", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Grupo de Ocorrência"
        verbose_name_plural = "Grupos de Ocorrência"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome or f"Grupo #{self.pk}"


class CodigoOcorrencia(models.Model):
    """
    Código de ocorrência pertencente a um grupo.
    Ex.: sigla=VIA-01, descricao="Apoio de Viatura"
    """
    grupo = models.ForeignKey(
        GrupoOcorrencia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="codigos",
    )
    sigla = models.CharField("Sigla", max_length=30, default="")
    descricao = models.CharField("Descrição", max_length=255, default="")

    class Meta:
        verbose_name = "Código de Ocorrência"
        verbose_name_plural = "Códigos de Ocorrência"
        ordering = ["sigla"]
        indexes = [
            models.Index(fields=["sigla"]),
            models.Index(fields=["descricao"]),
        ]

    def __str__(self) -> str:
        if self.sigla and self.descricao:
            return f"{self.sigla} — {self.descricao}"
        return self.sigla or self.descricao or f"Código #{self.pk}"


# ==============
#     Talão
# ==============

STATUS_CHOICES = (
    ("ABERTO", "ABERTO"),
    ("FECHADO", "FECHADO"),
)


class Talao(models.Model):
    """
    Registro de talão de viatura.
    Pensado para funcionar com os templates/listas já enviados.
    """

    # Referências
    viatura = models.ForeignKey(
        "viaturas.Viatura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taloes",
        verbose_name="Viatura",
    )
    codigo_ocorrencia = models.ForeignKey(
        CodigoOcorrencia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taloes",
        verbose_name="Código de ocorrência",
    )

    # Situação
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="ABERTO",
    )
    iniciado_em = models.DateTimeField(
        "Iniciado em",
        default=timezone.now,  # garante valor mesmo se a view não setar
        db_index=True,
    )
    encerrado_em = models.DateTimeField("Encerrado em", null=True, blank=True)

    # Quilometragem
    km_inicial = models.IntegerField("KM inicial", null=True, blank=True)
    km_final = models.IntegerField("KM final", null=True, blank=True)

    # Local
    local_bairro = models.CharField("Bairro", max_length=100, blank=True, default="")
    local_rua = models.CharField("Rua/Logradouro", max_length=200, blank=True, default="")

    # Plantão / Equipe da sessão (string consolidada)
    plantao = models.CharField("Plantão", max_length=30, blank=True, default="")
    talao_numero = models.PositiveIntegerField("Número seq. no plantão", default=1, help_text="Sequência reinicia a cada plantão")
    equipe_texto = models.CharField(
        "Equipe (texto)",
        max_length=255,
        blank=True,
        default="",
        help_text="Texto consolidado da equipe (encarregado, motorista, auxiliares).",
    )

    # (Opcional) vínculos de pessoal — úteis para filtros por usuário
    encarregado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taloes_encarregado",
        verbose_name="Encarregado",
    )
    motorista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taloes_motorista",
        verbose_name="Motorista",
    )
    auxiliar1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taloes_auxiliar1",
        verbose_name="Auxiliar 1",
    )
    auxiliar2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taloes_auxiliar2",
        verbose_name="Auxiliar 2",
    )

    # Quem abriu o talão (deixa opcional para evitar IntegrityError)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taloes_criados",
        verbose_name="Criado por",
    )

    class Meta:
        verbose_name = "Talão"
        verbose_name_plural = "Talões"
        ordering = ["-iniciado_em"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["iniciado_em"]),
            models.Index(fields=["viatura"]),
        ]

    # -------- helpers --------
    def __str__(self) -> str:
        return f"Talão #{self.pk or 'novo'}"

    @property
    def km_display(self) -> str:
        """Exibe KM como '12345 → 12800' (ou só o inicial)."""
        if self.km_inicial is None:
            return "-"
        if self.km_final is None:
            return f"{self.km_inicial}"
        return f"{self.km_inicial} → {self.km_final}"

    @property
    def local_display(self) -> str:
        """Combina bairro/rua para uso em listas."""
        if self.local_bairro and self.local_rua:
            return f"{self.local_bairro} — {self.local_rua}"
        return self.local_bairro or self.local_rua or "-"


# ==============
#   Abordados
# ==============

class Abordado(models.Model):
    """
    Pessoa ou veículo abordado durante um talão.
    """
    talao = models.ForeignKey(
        Talao,
        on_delete=models.CASCADE,
        related_name="abordados",
        verbose_name="Talão",
    )
    
    # Tipo: pessoa ou veículo
    tipo = models.CharField(
        "Tipo",
        max_length=10,
        choices=[
            ("PESSOA", "Pessoa"),
            ("VEICULO", "Veículo"),
        ],
        default="PESSOA",
    )
    
    # Dados da pessoa
    nome = models.CharField("Nome", max_length=200, blank=True, default="")
    documento = models.CharField("RG/CPF", max_length=50, blank=True, default="")
    
    # Dados do veículo
    placa = models.CharField("Placa", max_length=10, blank=True, default="")
    modelo = models.CharField("Modelo", max_length=100, blank=True, default="")
    cor = models.CharField("Cor", max_length=50, blank=True, default="")
    
    # Observações gerais
    observacoes = models.TextField("Observações", blank=True, default="")
    
    # Timestamp
    criado_em = models.DateTimeField("Criado em", default=timezone.now)
    
    class Meta:
        verbose_name = "Abordado"
        verbose_name_plural = "Abordados"
        ordering = ["criado_em"]
    
    def __str__(self) -> str:
        if self.tipo == "PESSOA":
            return f"{self.nome or 'Pessoa'} ({self.documento or 'sem doc'})"
        else:
            return f"{self.placa or 'Veículo'} - {self.modelo or 'sem modelo'}"


# =============================
#  Checklist de Viatura (Avarias)
# =============================
class ChecklistViatura(models.Model):
    """Checklist de avarias da viatura no plantão (marca somente o que tem problema)."""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='checklists_viatura')
    data = models.DateField(db_index=True)
    plantao_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    radio_comunicador = models.BooleanField(default=False)
    sistema_luminoso = models.BooleanField(default=False)
    bancos = models.BooleanField(default=False)
    tapetas = models.BooleanField(default=False)
    painel = models.BooleanField(default=False)
    limpeza_interna = models.BooleanField(default=False)
    antena = models.BooleanField(default=False)
    pneus = models.BooleanField(default=False)
    calotas = models.BooleanField(default=False)
    rodas_liga = models.BooleanField(default=False)
    para_brisa = models.BooleanField(default=False)
    palhetas_dianteiras = models.BooleanField(default=False)
    palheta_traseira = models.BooleanField(default=False)
    farois_dianteiros = models.BooleanField(default=False)
    farois_neblina = models.BooleanField(default=False)
    lanternas_traseiras = models.BooleanField(default=False)
    luz_re = models.BooleanField(default=False)
    sensor_estacionamento = models.BooleanField(default=False)
    portinhola_tanque = models.BooleanField(default=False)
    fluido_freio = models.BooleanField(default=False)
    liquido_arrefecimento = models.BooleanField(default=False)
    fluido_direcao = models.BooleanField(default=False)
    bateria = models.BooleanField(default=False)
    amortecedor = models.BooleanField(default=False)
    tampa_porta_malas = models.BooleanField(default=False)
    estepe = models.BooleanField(default=False)
    triangulo = models.BooleanField(default=False)
    chave_rodas = models.BooleanField(default=False)
    macaco = models.BooleanField(default=False)
    suspensao = models.BooleanField(default=False)
    documentacao = models.BooleanField(default=False)
    oleo = models.BooleanField(default=False)
    # Campo livre para outras avarias não listadas
    outros = models.TextField("Outros (descrever)", blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("usuario", "data")
        verbose_name = "Checklist de Viatura"
        verbose_name_plural = "Checklists de Viatura"

    def itens_marcados(self):
        mapping = {
            'radio_comunicador': 'Rádio Comunicador',
            'sistema_luminoso': 'Sistema Luminoso (High Light)',
            'bancos': 'Bancos',
            'tapetas': 'Tapetas',
            'painel': 'Painel',
            'limpeza_interna': 'Limpeza Interna',
            'antena': 'Antena',
            'pneus': 'Pneus',
            'calotas': 'Calotas',
            'rodas_liga': 'Rodas de Liga',
            'para_brisa': 'Para-brisa',
            'palhetas_dianteiras': 'Palhetas dianteiras',
            'palheta_traseira': 'Palheta Traseira',
            'farois_dianteiros': 'Faróis/Piscas Dianteiros',
            'farois_neblina': 'Faróis de Neblina',
            'lanternas_traseiras': 'Lanterna/Piscas Traseiros',
            'luz_re': 'Luz de Ré',
            'sensor_estacionamento': 'Sensor de Estacionamento',
            'portinhola_tanque': 'Portinhola Tanque Combustível',
            'fluido_freio': 'Fluido de Freio',
            'liquido_arrefecimento': 'Líquido de Arrefecimento',
            'fluido_direcao': 'Fluido Direção Hidráulica',
            'bateria': 'Bateria (Controle Visual)',
            'amortecedor': 'Amortecedor',
            'tampa_porta_malas': 'Tampa do Porta-Malas',
            'estepe': 'Estepe',
            'triangulo': 'Triângulo',
            'chave_rodas': 'Chave de Rodas',
            'macaco': 'Macaco',
            'suspensao': 'Suspensão (Barulhos)',
            'documentacao': 'Documentação',
            'oleo': 'Óleo (nível e troca)',
        }
        itens = [label for field, label in mapping.items() if getattr(self, field)]
        txt = (self.outros or "").strip()
        if txt:
            itens.append(f"Outros: {txt}")
        return itens


class AvariaLog(models.Model):
    """Registro histórico de avarias reportadas no checklist, por submissão.

    Mantém o histórico mesmo após resolução para auditoria/controle.
    """
    viatura = models.ForeignKey(
        "viaturas.Viatura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avarias_logs",
    )
    plantao_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    data = models.DateField(db_index=True)
    itens_json = models.TextField(blank=True, default="")  # JSON com lista de labels
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["data", "plantao_id"])]

    def itens(self):
        import json
        try:
            return json.loads(self.itens_json or "[]")
        except Exception:
            return []


class AvariaAnexo(models.Model):
    """Anexo (foto/arquivo) de uma avaria específica do checklist."""
    checklist = models.ForeignKey(
        ChecklistViatura,
        on_delete=models.CASCADE,
        related_name='anexos'
    )
    campo_avaria = models.CharField(
        max_length=100,
        help_text='Nome do campo de avaria (ex: radio_comunicador, sistema_luminoso)',
        db_index=True
    )
    arquivo = models.FileField(
        upload_to='avarias/%Y/%m/',
        help_text='Foto ou arquivo da avaria'
    )
    descricao = models.CharField(max_length=255, blank=True, help_text='Descrição opcional')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em']
        verbose_name = 'Anexo de Avaria'
        verbose_name_plural = 'Anexos de Avarias'
        indexes = [
            models.Index(fields=['checklist', 'campo_avaria']),
        ]

    def __str__(self):
        return f"Anexo {self.campo_avaria} - Checklist #{self.checklist_id}"
    
    @property
    def campo_label(self):
        """Retorna o label amigável do campo"""
        mapping = {
            'radio_comunicador': 'Rádio Comunicador',
            'sistema_luminoso': 'Sistema Luminoso (High Light)',
            'bancos': 'Bancos',
            'tapetas': 'Tapetas',
            'painel': 'Painel',
            'limpeza_interna': 'Limpeza Interna',
            'antena': 'Antena',
            'pneus': 'Pneus',
            'calotas': 'Calotas',
            'rodas_liga': 'Rodas de Liga',
            'para_brisa': 'Para-brisa',
            'palhetas_dianteiras': 'Palhetas dianteiras',
            'palheta_traseira': 'Palheta Traseira',
            'farois_dianteiros': 'Faróis/Piscas Dianteiros',
            'farois_neblina': 'Faróis de Neblina',
            'lanternas_traseiras': 'Lanterna/Piscas Traseiros',
            'luz_re': 'Luz de Ré',
            'sensor_estacionamento': 'Sensor de Estacionamento',
            'portinhola_tanque': 'Portinhola Tanque Combustível',
            'fluido_freio': 'Fluido de Freio',
            'liquido_arrefecimento': 'Líquido de Arrefecimento',
            'fluido_direcao': 'Fluido Direção Hidráulica',
            'bateria': 'Bateria (Controle Visual)',
            'amortecedor': 'Amortecedor',
            'tampa_porta_malas': 'Tampa do Porta-Malas',
            'estepe': 'Estepe',
            'triangulo': 'Triângulo',
            'chave_rodas': 'Chave de Rodas',
            'macaco': 'Macaco',
            'suspensao': 'Suspensão (Barulhos)',
            'documentacao': 'Documentação',
            'oleo': 'Óleo (nível e troca)',
        }
        return mapping.get(self.campo_avaria, self.campo_avaria.replace('_', ' ').title())


# =============================
#  Abastecimento de Combustível
# =============================
class Abastecimento(models.Model):
    """Registro de abastecimento vinculado a um Talão.
    Campos mínimos conforme solicitação: número da requisição, tipo de combustível,
    litros e recibo do posto (anexo)."""

    COMBUSTIVEL_CHOICES = [
        ("GASOLINA", "Gasolina"),
        ("ETANOL", "Etanol"),
        ("DIESEL", "Diesel"),
    ]

    talao = models.ForeignKey(
        Talao,
        on_delete=models.CASCADE,
        related_name="abastecimentos",
        verbose_name="Talão",
        db_index=True,
    )

    requisicao_numero = models.CharField("Nº da Requisição", max_length=50, blank=True, default="")
    tipo_combustivel = models.CharField("Tipo de Combustível", max_length=10, choices=COMBUSTIVEL_CHOICES)
    litros = models.DecimalField("Litros", max_digits=7, decimal_places=2)
    recibo_do_posto = models.FileField(
        "Recibo do Posto",
        upload_to="abastecimentos/%Y/%m/",
        blank=True,
        null=True,
    )

    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Abastecimento"
        verbose_name_plural = "Abastecimentos"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["talao", "criado_em"]),
        ]

    def __str__(self) -> str:
        return f"Abastecimento {self.requisicao_numero or ''} ({self.get_tipo_combustivel_display()}) - {self.litros} L"


# =============================
#  AITs emitidas por Talão
# =============================
class AitRegistro(models.Model):
    """Número de AIT emitida no contexto de um Talão."""
    talao = models.ForeignKey(
        Talao,
        on_delete=models.CASCADE,
        related_name="aits",
        verbose_name="Talão",
        db_index=True,
    )
    integrante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aits_registradas",
        verbose_name="Integrante",
    )
    numero = models.CharField("Número da AIT", max_length=50)
    criado_em = models.DateTimeField("Criado em", default=timezone.now)

    class Meta:
        verbose_name = "AIT do Talão"
        verbose_name_plural = "AITs do Talão"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["talao", "numero"], name="uniq_talao_numero_ait")
        ]

    def __str__(self) -> str:
        return f"AIT {self.numero} (Talão {getattr(self.talao,'pk','?')})"

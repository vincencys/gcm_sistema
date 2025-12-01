from __future__ import annotations
from django.conf import settings
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from common.models import SoftDeleteModel, TimeStamped
from django.conf import settings


# ========
# ESTOQUE
# ========
class CategoriaProduto(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Categoria de Produto"
        verbose_name_plural = "Categorias de Produto"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Produto(models.Model):
    categoria = models.ForeignKey(CategoriaProduto, on_delete=models.SET_NULL, null=True, blank=True, related_name="produtos")
    nome = models.CharField(max_length=150)
    unidade = models.CharField(max_length=20, blank=True, default="un")  # ex.: un, cx, kg, L
    estoque_atual = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    estoque_minimo = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["nome"]
        indexes = [models.Index(fields=["nome"]), models.Index(fields=["ativo"])]

    def __str__(self) -> str:
        return self.nome

    @property
    def baixo_estoque(self) -> bool:
        try:
            return self.estoque_atual <= self.estoque_minimo
        except Exception:
            return False


class MovimentacaoEstoque(models.Model):
    TIPOS = (
        ("ENTRADA", "Entrada"),
        ("SAIDA", "Saída"),
        ("AJUSTE", "Ajuste"),
    )
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo = models.CharField(max_length=10, choices=TIPOS)
    quantidade = models.DecimalField(max_digits=12, decimal_places=3)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    observacao = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Movimentação de Estoque"
        verbose_name_plural = "Movimentações de Estoque"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["produto", "criado_em"])]
        permissions = (
            ("movimentar_estoque", "Pode movimentar estoque de munição/itens"),
            ("ver_livro_municao", "Pode visualizar o livro/relatórios de munição"),
        )

    def aplicar_no_saldo(self):
        # Convenção: ENTRADA +, SAIDA -, AJUSTE aplica quantidade como delta direto
        p = self.produto
        if self.tipo == "ENTRADA":
            p.estoque_atual = (p.estoque_atual or 0) + self.quantidade
        elif self.tipo == "SAIDA":
            p.estoque_atual = (p.estoque_atual or 0) - self.quantidade
        else:
            p.estoque_atual = (p.estoque_atual or 0) + self.quantidade
        p.save(update_fields=["estoque_atual"])  # mantém simples


# =========
# CAUTELAS
# =========
class BemPatrimonial(models.Model):
    TIPOS = (
        ("ARMA", "Arma"),
        ("COLETE", "Colete"),
        ("TABLET", "Tablet"),
        ("VEICULO", "Veículo"),
        ("RADIO", "Rádio"),
        ("CONE", "Cone"),
        ("OUTRO", "Outro"),
    )
    GRUPOS = (
        ("SUPORTE", "Suporte"),
        ("FIXO", "Fixo"),
    )
    CLASSES = (
        ("ARMAMENTO", "Armamento"),
        ("MUNICAO", "Munição"),
        ("PLACA_BALISTICA", "Placa Balística"),
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    # Novos campos para organizar as listas de cautelas
    grupo = models.CharField(max_length=10, choices=GRUPOS, default="SUPORTE")
    classe = models.CharField(max_length=20, choices=CLASSES, default="ARMAMENTO")
    subtipo_armamento = models.CharField(
        max_length=10,
        blank=True,
        default="",
        choices=(
            ("PISTOLA", "Pistola"),
            ("REVOLVER", "Revólver"),
            ("CTT", "Carabina"),
            ("CAL12", "Espingarda"),
            ("FUZIL", "Fuzil"),
        ),
    )
    nome = models.CharField(max_length=150)
    tombamento = models.CharField(max_length=100, blank=True, default="")
    numero_serie = models.CharField(max_length=100, blank=True, default="")
    # Para itens de munição cadastrados como BemPatrimonial
    lote = models.CharField(max_length=60, blank=True, default="")
    calibre = models.CharField(max_length=20, blank=True, default="")  # quando ARMA
    # Para itens de classe MUNICAO, representa a quantidade disponível/cadastrada do item
    quantidade = models.PositiveIntegerField(default=0)
    observacoes = models.CharField(max_length=255, blank=True, default="")
    # Campos específicos para Placa Balística
    placa_marca = models.CharField(max_length=100, blank=True, default="")
    placa_modelo = models.CharField(max_length=100, blank=True, default="")
    placa_numero = models.CharField(max_length=100, blank=True, default="")
    placa_nivel = models.CharField(max_length=20, blank=True, default="")  # ex: II-A, III-A, III, IV
    placa_tamanho = models.CharField(
        max_length=10,
        blank=True,
        default="",
        choices=(
            ("PP", "PP"),
            ("P", "P"),
            ("M", "M"),
            ("G", "G"),
            ("GG", "GG"),
        ),
    )
    # Dono/Responsável (usado principalmente para itens do grupo FIXO)
    dono = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bens_proprios",
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Bem Patrimonial"
        verbose_name_plural = "Bens Patrimoniais"
        ordering = ["tipo", "nome"]
        indexes = [
            models.Index(fields=["tipo"]),
            models.Index(fields=["tombamento"]),
            models.Index(fields=["numero_serie"]),
            models.Index(fields=["lote"]),
            models.Index(fields=["grupo", "classe"]),
            models.Index(fields=["dono"]),
        ]

    def __str__(self) -> str:
        base = f"{self.get_tipo_display()} - {self.nome}"
        if self.tombamento:
            base += f" (Tombo {self.tombamento})"
        return base


class CautelaPermanente(models.Model):
    bem = models.ForeignKey(BemPatrimonial, on_delete=models.CASCADE, related_name="cautelas_permanentes")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    atribuido_em = models.DateTimeField(default=timezone.now)
    devolvido_em = models.DateTimeField(null=True, blank=True)
    observacao = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Cautela Permanente"
        verbose_name_plural = "Cautelas Permanentes"
        ordering = ["-atribuido_em"]
        indexes = [models.Index(fields=["bem", "usuario", "atribuido_em"])]
        permissions = (
            ("gerir_assignacoes_fixas", "Pode criar/encerrar termos de responsabilidade (fixo)"),
            ("verificacao_periodica", "Pode realizar verificação periódica de armamento fixo"),
        )

    @property
    def em_posse(self) -> bool:
        return self.devolvido_em is None


class MovimentacaoCautela(models.Model):
    TIPOS = (
        ("SAIDA", "Saída"),
        ("ENTRADA", "Entrada"),
    )
    bem = models.ForeignKey(BemPatrimonial, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo = models.CharField(max_length=7, choices=TIPOS)
    agente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="cautelas_agente")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="cautelas_registrador")
    checklist_saida_json = models.TextField(blank=True, default="")
    checklist_entrada_json = models.TextField(blank=True, default="")
    observacao = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Movimentação de Cautela"
        verbose_name_plural = "Movimentações de Cautela"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["bem", "criado_em"])]
        permissions = (
            ("aprovar_cautela", "Pode aprovar solicitações de cautela"),
            ("entregar_cautela", "Pode entregar/abrir cautela"),
            ("devolver_cautela", "Pode receber/devolver e encerrar cautela"),
            ("desbloquear_excecao", "Pode desbloquear exceções (atrasos/fora de horário)"),
            ("ver_auditoria", "Pode visualizar trilhas de auditoria relacionadas"),
        )


class DisparoArma(models.Model):
    bem = models.ForeignKey(BemPatrimonial, on_delete=models.CASCADE, related_name="disparos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    quantidade = models.PositiveIntegerField(default=0)
    data = models.DateField(default=timezone.localdate)
    observacao = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Disparo de Arma"
        verbose_name_plural = "Disparos de Arma"
        ordering = ["-data", "-id"]
        indexes = [models.Index(fields=["bem", "data"])]


# =====================
# NOVOS MODELOS (MVP)
# =====================

class Municao(SoftDeleteModel, TimeStamped):
    TIPO_CHOICES = (
        ("TREINO", "Treino"),
        ("OPERACIONAL", "Operacional"),
    )
    STATUS_CHOICES = (
        ("ATIVO", "Ativo"),
        ("INATIVO", "Inativo"),
    )

    calibre = models.CharField(max_length=20, db_index=True)
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES, default="OPERACIONAL")
    lote = models.CharField(max_length=60, db_index=True)
    validade = models.DateField(null=True, blank=True)
    unidade_medida = models.CharField(max_length=10, default="un")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ATIVO")

    class Meta:
        verbose_name = "Munição"
        verbose_name_plural = "Munições"
        ordering = ["calibre", "lote"]
        indexes = [
            models.Index(fields=["calibre", "lote"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.calibre} {self.tipo} - lote {self.lote}"


class MunicaoEstoque(SoftDeleteModel, TimeStamped):
    municao = models.ForeignKey(Municao, on_delete=models.CASCADE, related_name="estoques")
    local = models.CharField(max_length=80, default="ALMOXARIFADO", db_index=True)
    quantidade_disponivel = models.PositiveIntegerField(default=0)
    quantidade_reservada = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Estoque de Munição"
        verbose_name_plural = "Estoques de Munição"
        unique_together = ("municao", "local")
        indexes = [models.Index(fields=["local"]) ]

    def __str__(self) -> str:
        return f"{self.local}: {self.municao} (disp {self.quantidade_disponivel} / res {self.quantidade_reservada})"


class Cautela(SoftDeleteModel, TimeStamped):
    TIPO_CHOICES = (
        ("SUPORTE", "Suporte"),
        ("FIXO", "Fixo"),
    )
    STATUS_CHOICES = (
        ("PENDENTE", "Pendente Aprovação"),
        ("APROVADA", "Aprovada"),
        ("ABERTA", "Aberta"),
        ("ENCERRADA", "Encerrada"),
        ("ATRASADA", "Atrasada"),
        ("CANCELADA", "Cancelada"),
    )

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cautelas_usuario")
    almoxarife = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cautelas_almoxarife", null=True, blank=True)
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cautelas_supervisor", null=True, blank=True)
    data_hora_retirada = models.DateTimeField(null=True, blank=True)
    data_hora_prevista_devolucao = models.DateTimeField(null=True, blank=True)
    data_hora_devolucao = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDENTE", db_index=True)
    motivo = models.CharField(max_length=255, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    rev = models.PositiveIntegerField(default=1, help_text="Versão para controle otimista")
    aprovada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Cautela"
        verbose_name_plural = "Cautelas"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["tipo", "status"]),
            models.Index(fields=["usuario", "status"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Cautela #{self.id} ({self.get_tipo_display()} - {self.get_status_display()})"


class CautelaItem(SoftDeleteModel, TimeStamped):
    ITEM_TIPO_CHOICES = (
        ("ARMAMENTO", "Armamento"),
        ("MUNICAO", "Munição"),
        ("ACESSORIO", "Acessório"),
    )
    cautela = models.ForeignKey(Cautela, on_delete=models.CASCADE, related_name="itens")

    # Generic FK p/ apontar para BemPatrimonial (armas/acessórios) ou Municao
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    item = GenericForeignKey('content_type', 'object_id')

    item_tipo = models.CharField(max_length=12, choices=ITEM_TIPO_CHOICES)
    quantidade = models.PositiveIntegerField(default=1)
    estado_saida = models.CharField(max_length=120, blank=True, default="")
    estado_retorno = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        verbose_name = "Item de Cautela"
        verbose_name_plural = "Itens de Cautela"
        indexes = [models.Index(fields=["cautela"]) ]


class AssignacaoFixa(SoftDeleteModel, TimeStamped):
    STATUS_CHOICES = (
        ("ATIVA", "Ativa"),
        ("ENCERRADA", "Encerrada"),
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    armamento = models.ForeignKey(BemPatrimonial, on_delete=models.PROTECT, limit_choices_to={"classe": "ARMAMENTO"})
    termo_pdf = models.FileField(upload_to="termos_fixo/", null=True, blank=True)
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ATIVA")

    class Meta:
        verbose_name = "Assignação Fixa"
        verbose_name_plural = "Assignações Fixas"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["usuario", "status"]) ]


class Manutencao(SoftDeleteModel, TimeStamped):
    TIPO_CHOICES = (
        ("PREVENTIVA", "Preventiva"),
        ("CORRETIVA", "Corretiva"),
        ("BAIXA", "Baixa"),
    )

    armamento = models.ForeignKey(BemPatrimonial, on_delete=models.CASCADE, related_name="manutencoes", limit_choices_to={"classe": "ARMAMENTO"})
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    responsavel = models.CharField(max_length=120, blank=True, default="")
    observacoes = models.CharField(max_length=255, blank=True, default="")
    impacta_disponibilidade = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Manutenção"
        verbose_name_plural = "Manutenções"
        ordering = ("-data_inicio", "-id")
        indexes = [models.Index(fields=["armamento", "data_inicio"]) ]


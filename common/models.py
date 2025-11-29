from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
import hashlib
import json

User = get_user_model()


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.exclude(deleted_at__isnull=True)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        # Retorna apenas registros não deletados por padrão
        return super().get_queryset().filter(deleted_at__isnull=True)

    def all_with_deleted(self):
        return super().get_queryset()


class SoftDeleteModel(models.Model):
    """Modelo base com soft delete simples via campo deleted_at.

    - Manager padrão retorna apenas registros ativos (deleted_at is null)
    - Para incluir deletados, use `.all_with_deleted()`
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):  # pragma: no cover
        from django.utils import timezone
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])


class Assinavel(models.Model):
    assinatura_img = models.ImageField(upload_to='assinaturas/', null=True, blank=True)
    assinado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    assinado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class NaturezaOcorrencia(models.Model):
    grupo = models.CharField(max_length=20, db_index=True)        # ex.: ALFA
    grupo_nome = models.CharField(max_length=120)                  # ex.: OCORRÊNCIA CONTRA PESSOAS
    codigo = models.CharField(max_length=10, unique=True, db_index=True)  # ex.: A-01
    titulo = models.CharField(max_length=200)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ("grupo", "codigo")
        verbose_name = "Natureza de ocorrência"
        verbose_name_plural = "Naturezas de ocorrência"

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"


class DocumentoAssinavel(TimeStamped):
    TIPO_CHOICES = (
        ("PLANTAO", "Relatório de Plantão"),
        ("BOGCMI", "BOGCMI"),
        ("LIVRO_CECOM", "Livro CECOM"),
    )
    STATUS_CHOICES = (
        ("PENDENTE", "Pendente Assinatura Comando"),  # legacy
        ("ASSINADO", "Despachado / Arquivado"),        # legacy
        ("PENDENTE_ADM", "Pendente Assinatura do Administrativo"),
        ("ASSINADO_ADM", "Despacho / Assinatura do Administrativo"),
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    usuario_origem = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documentos_emitidos")
    arquivo = models.FileField(upload_to="documentos/origem/")
    arquivo_assinado = models.FileField(upload_to="documentos/assinados/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDENTE", db_index=True)
    encarregado_assinou = models.BooleanField(default=False)
    comando_assinou = models.BooleanField(default=False)
    comando_assinou_em = models.DateTimeField(null=True, blank=True)
    comando_usuario = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="documentos_assinados")
    observacao = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_tipo_display()} #{self.id} ({self.get_status_display()})"

    @property
    def nome_arquivo(self):
        return self.arquivo.name.split('/')[-1]

    @property
    def bo_numero(self):
        """Retorna o número do BO (ex.: 64-2025) a partir do nome do arquivo.

        Suporta padrões antigos e novos:
          Antigo: *_BOGCM_<pk>.pdf
          Novo:   *_BOGCM_<numero>.pdf  (onde <numero> contém sequência-ano)
          Fallback: se apenas dígitos e não for formato numero-ano, tenta tratar como pk.
        """
        if self.tipo != 'BOGCMI':
            return ''
        if hasattr(self, '_bo_num_cache'):
            return getattr(self, '_bo_num_cache')
        try:
            import re
            fname = self.nome_arquivo
            m_new = re.search(r'BOGCMI?_(\d+-\d{4})', fname)
            if m_new:
                self._bo_num_cache = m_new.group(1)
                return self._bo_num_cache
            m_old = re.search(r'BOGCM_(\d+)', fname)
            if not m_old:
                self._bo_num_cache = ''
                return ''
            ident = m_old.group(1)
            from bogcmi.models import BO  # lookup pk -> numero (se existir)
            bo = BO.objects.filter(pk=ident).only('numero').first()
            if bo and bo.numero:
                self._bo_num_cache = bo.numero
                return self._bo_num_cache
            self._bo_num_cache = ident
            return ident
        except Exception:
            return ''


class AuditLog(models.Model):
    """Registro de auditoria de ações de usuários.

    Guarda o essencial para rastreabilidade: quem, quando, o quê e de onde.
    """
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=512)
    action = models.CharField(max_length=120, blank=True, help_text="Descrição resumida da ação (opcional)")
    querystring = models.CharField(max_length=1000, blank=True)
    body = models.TextField(blank=True, help_text="Corpo da requisição (truncado)")
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["method"]),
            models.Index(fields=["path"]),
        ]

    def __str__(self) -> str:
        u = getattr(self.user, 'username', 'anon')
        return f"[{self.created_at:%Y-%m-%d %H:%M:%S}] {u} {self.method} {self.path}"


class PushDevice(models.Model):
    """Dispositivo para envio de notificações push (FCM).

    Um token pode estar associado a apenas um registro (unique). O mesmo usuário pode ter
    vários dispositivos. Plataforma indica 'android', 'ios' ou 'web'.
    """
    PLATFORM_CHOICES = (
        ("android", "Android"),
        ("ios", "iOS"),
        ("web", "Web"),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_devices", null=True, blank=True)
    token = models.CharField(max_length=255, unique=True, db_index=True)
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES, default="android")
    app_version = models.CharField(max_length=32, blank=True)
    device_info = models.CharField(max_length=255, blank=True, help_text="Modelo/OS/identificação livre")
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_seen",)
        indexes = [
            models.Index(fields=["user", "platform"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.platform}:{self.user_id}:{self.token[:8]}…"


class AuditTrail(TimeStamped):
    """Trilha de auditoria forte (append-only) com hash encadeado.

    - Encadeamento: hash_atual = SHA256(prev_hash + timestamp + actor_id + app.model + object_id + event + before + after)
    - Campos before/after armazenados como JSON textual para inspeção.
    - Proíbe updates após criação (append-only); deleção deve ser evitada (sem cascade).
    """

    EVENT_CHOICES = (
        ("SOLICITAR", "Solicitar"),
        ("APROVAR", "Aprovar"),
        ("ENTREGAR", "Entregar"),
        ("DEVOLVER", "Devolver"),
        ("OUTRO", "Outro"),
    )

    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    obj = GenericForeignKey("content_type", "object_id")

    event = models.CharField(max_length=16, choices=EVENT_CHOICES, default="OUTRO", db_index=True)
    message = models.CharField(max_length=255, blank=True)

    before = models.TextField(blank=True, help_text="Snapshot anterior em JSON")
    after = models.TextField(blank=True, help_text="Snapshot posterior em JSON")

    hash_prev = models.CharField(max_length=64, blank=True, db_index=True)
    hash_current = models.CharField(max_length=64, db_index=True)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["content_type", "object_id", "created_at"]),
            models.Index(fields=["event", "created_at"]),
        ]

    def save(self, *args, **kwargs):  # pragma: no cover
        # Append-only: impedir alterações após criado
        if self.pk:
            raise RuntimeError("AuditTrail é append-only; atualizações não são permitidas")
        # Calcular hash
        prev = self.hash_prev or ""
        ts = (self.created_at or timezone.now()).isoformat()
        actor_id = str(self.actor_id or "0")
        ident = f"{self.content_type.app_label}.{self.content_type.model}:{self.object_id}"
        payload = (prev + ts + actor_id + ident + (self.event or "") + (self.before or "") + (self.after or "")).encode("utf-8", errors="ignore")
        self.hash_current = hashlib.sha256(payload).hexdigest()
        super().save(*args, **kwargs)

    @staticmethod
    def latest_hash_for(obj) -> str:
        ct = ContentType.objects.get_for_model(obj.__class__)
        last = AuditTrail.objects.filter(content_type=ct, object_id=obj.pk).only("hash_current").order_by("-created_at", "-id").first()
        return last.hash_current if last else ""

    @staticmethod
    def dumps(data) -> str:
        try:
            return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return ""


class SimpleLog(models.Model):
    """Log simplificado e legível para operações do sistema.

    Focado em mensagem humana, evento, alvo opcional e metadados essenciais.
    Mantém um link genérico para o objeto alvo quando aplicável.
    """

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    app_label = models.CharField(max_length=50, db_index=True)
    event = models.CharField(max_length=50, db_index=True)
    message = models.CharField(max_length=255, blank=True)

    # Alvo genérico (opcional)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    obj = GenericForeignKey("content_type", "object_id")
    target_repr = models.CharField(max_length=255, blank=True, help_text="Representação curta do alvo")

    # Metadados de requisição
    path = models.CharField(max_length=512, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    extra = models.TextField(blank=True, help_text="JSON textual opcional com dados extras")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["app_label", "event", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        u = getattr(self.user, 'username', 'anon')
        tgt = f" {self.target_repr}" if self.target_repr else ""
        return f"[{self.created_at:%Y-%m-%d %H:%M:%S}] {u} {self.app_label}:{self.event}{tgt}"

    @staticmethod
    def dumps(data) -> str:
        try:
            return json.dumps(data or {}, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return ""


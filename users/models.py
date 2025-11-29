# users/models.py
from __future__ import annotations

from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from common.models import TimeStamped, SoftDeleteModel

User = get_user_model()
class Lotacao(SoftDeleteModel, TimeStamped):
    nome = models.CharField(max_length=120)
    sigla = models.CharField(max_length=20, blank=True, db_index=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Lotação"
        verbose_name_plural = "Lotações"
        ordering = ("nome",)
        indexes = [models.Index(fields=["sigla"]) ]

    def __str__(self) -> str:
        return f"{self.sigla} - {self.nome}" if self.sigla else self.nome



def assinatura_upload_to(instance: "Perfil", filename: str) -> str:
    uid = instance.user_id or "anon"
    return f"assinaturas/{uid}/{filename}"


class Perfil(TimeStamped):
    EQUIPE_CHOICES = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")]
    CLASSE_CHOICES = [
        ("3C", "3ª Classe"),
        ("2C", "2ª Classe"),
        ("1C", "1ª Classe"),
        ("CD", "Classe Distinta"),
        ("CE", "Classe Especial"),
        ("SUB", "Subinspetor"),
        ("INS", "Inspetor"),
        ("SCM", "Sub CMT"),
        ("CMT", "CMT"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil",
        verbose_name="Usuário",
    )
    matricula = models.CharField("Matrícula", max_length=20, blank=True)
    equipe = models.CharField("Equipe", max_length=1, choices=EQUIPE_CHOICES, blank=True)
    classe = models.CharField("Classe", max_length=3, choices=CLASSE_CHOICES, blank=True)
    cargo = models.CharField("Cargo", max_length=80, default="Guarda Civil Municipal")
    lotacao = models.ForeignKey(
        Lotacao,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="perfis",
    )

    assinatura_img = models.ImageField(
        "Assinatura (PNG/JPG)",
        upload_to=assinatura_upload_to,
        null=True,
        blank=True,
    )
    assinatura_digital = models.TextField(
        "Assinatura Digital (Base64)",
        blank=True,
        help_text="Assinatura desenhada digitalmente"
    )
    recovery_email = models.EmailField(
        "Email de recuperação",
        blank=True,
        help_text="E-mail usado para recuperar a senha (opcional)."
    )
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        verbose_name = "Perfil GCM"
        verbose_name_plural = "Perfis GCM"
        ordering = ("user__username",)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.cargo})"

    @property
    def classe_legivel(self) -> str:
        return self.get_classe_display() if self.classe else ""

    @property
    def assinatura_url(self) -> str | None:
        return self.assinatura_img.url if self.assinatura_img else None


# cria/garante perfil ao criar usuário
@receiver(post_save, sender=User)
def criar_perfil_automatico(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.get_or_create(user=instance)


# --------- COMPATIBILIDADE COM CÓDIGO ANTIGO ----------
# Se algum lugar ainda referencia "GcmPerfil", esse alias resolve.
GcmPerfil = Perfil

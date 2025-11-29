from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import Perfil

User = get_user_model()

class GcmPerfilForm(forms.ModelForm):
    # Campo auxiliar (não-model) para escolher o modo de assinatura
    assinatura_tipo = forms.ChoiceField(
        choices=(
            ("upload", "Upload de imagem"),
            ("digital", "Assinatura digital"),
        ),
        required=False,
        widget=forms.RadioSelect,
        label="Tipo de assinatura",
    )

    class Meta:
        model = Perfil
        fields = [
            "matricula",
            "equipe",
            "classe",
            "cargo",
            "recovery_email",
            # campos de assinatura do modelo
            "assinatura_img",
            "assinatura_digital",
            "ativo",
        ]
        widgets = {
            "matricula": forms.TextInput(attrs={"class": "input w-full"}),
            "equipe": forms.Select(attrs={"class": "input w-full"}),
            "classe": forms.Select(attrs={"class": "input w-full"}),
            "cargo": forms.TextInput(attrs={"class": "input w-full"}),
            "recovery_email": forms.EmailInput(attrs={"class": "input w-full", "placeholder": "seu.email@exemplo.com"}),
            "assinatura_img": forms.ClearableFileInput(attrs={"class": "input w-full"}),
            # campo hidden que recebe o base64 gerado no canvas
            "assinatura_digital": forms.HiddenInput(),
            "ativo": forms.CheckboxInput(),
        }
        labels = {
            "recovery_email": "Email de recuperação",
        }

class RegistrarUsuarioForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

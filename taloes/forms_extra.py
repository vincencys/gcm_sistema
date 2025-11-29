from __future__ import annotations

from django import forms

from .models import Talao, CodigoOcorrencia
from viaturas.models import Viatura


# ======================
#   SETUP DO PLANTÃO
# ======================

class SetupPlantaoForm(forms.Form):
    viatura = forms.ModelChoiceField(
        queryset=Viatura.objects.all(),
        label="Viatura",
        required=True,
    )
    plantao = forms.CharField(
        max_length=20,
        required=False,
        label="Plantão",
        help_text="Ex.: A, B, C, D ou texto livre",
    )
    encarregado = forms.CharField(max_length=80, required=False, label="Encarregado")
    motorista   = forms.CharField(max_length=80, required=False, label="Motorista")
    auxiliar1   = forms.CharField(max_length=80, required=False, label="Auxiliar 1")
    auxiliar2   = forms.CharField(max_length=80, required=False, label="Auxiliar 2")


# ======================
#   ABRIR NOVO TALÃO
# ======================

class NovoTalaoForm(forms.ModelForm):
    # Campos extras para captura no momento da abertura:
    local_bairro = forms.CharField(
        max_length=120, required=False, label="Bairro / Local"
    )
    codigo_ocorrencia = forms.ModelChoiceField(
        queryset=CodigoOcorrencia.objects.all(),
        required=False,
        label="Código de Ocorrência",
    )

    class Meta:
        model = Talao
        # 'local_bairro' não é coluna; salvamos manualmente no save()
        fields = ["viatura", "km_inicial", "codigo_ocorrencia"]
        widgets = {
            "viatura": forms.Select(attrs={"class": "w-full"}),
            "km_inicial": forms.NumberInput(attrs={"class": "w-full"}),
            "codigo_ocorrencia": forms.Select(attrs={"class": "w-full"}),
        }

    def save(self, commit: bool = True) -> Talao:
        obj: Talao = super().save(commit=False)
        # Mapeia o campo extra para a coluna real 'local'
        obj.local = self.cleaned_data.get("local_bairro", "") or obj.local
        if commit:
            obj.save()
            # nenhum M2M para salvar aqui
        return obj


# ======================
#   RELATÓRIO DE RONDA (SESSÃO)
# ======================

class RelatorioRondaForm(forms.Form):
    texto = forms.CharField(
        label="Relatório de Ronda (rascunho do plantão)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "class": "w-full"}),
    )


# ==========================================================
#   OPCIONAIS: usados por algumas views de detalhe/finalizar
#   (evitam ImportError se o seu views.py importar estes)
# ==========================================================

class TalaoOcorrenciaForm(forms.ModelForm):
    local_bairro = forms.CharField(
        max_length=120, required=False, label="Bairro / Local"
    )

    class Meta:
        model = Talao
        fields = ["codigo_ocorrencia"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Preenche o campo exibido com o valor atual de 'local'
        if self.instance and self.instance.pk:
            self.fields["local_bairro"].initial = self.instance.local

    def save(self, commit: bool = True) -> Talao:
        obj: Talao = super().save(commit=False)
        obj.local = self.cleaned_data.get("local_bairro", "") or obj.local
        if commit:
            obj.save()
        return obj


class FinalizarTalaoForm(forms.ModelForm):
    class Meta:
        model = Talao
        fields = ["km_final"]

    def clean_km_final(self):
        km_final = self.cleaned_data.get("km_final")
        inst = getattr(self, "instance", None)
        km_ini = getattr(inst, "km_inicial", None)
        if km_final is None:
            raise forms.ValidationError("Informe o KM final para finalizar.")
        if km_ini is not None and km_final < km_ini:
            raise forms.ValidationError("KM final não pode ser menor que o KM inicial.")
        return km_final


class EditarRelatorioForm(forms.Form):
    texto = forms.CharField(
        label="Relatório",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "class": "w-full"}),
    )

# viaturas/forms.py
from django import forms
from .models import Viatura


class ViaturaForm(forms.ModelForm):
    class Meta:
        model = Viatura
        fields = [
            "prefixo", "placa", "status",
            "km_atual", "km_prox_troca_oleo", "km_prox_revisao",
            "observacoes", "ativo",
        ]

    def clean(self):
        data = super().clean()
        ka = data.get("km_atual") or 0
        kt = data.get("km_prox_troca_oleo")
        kr = data.get("km_prox_revisao")
        if kt is not None and kt < ka:
            self.add_error("km_prox_troca_oleo", "Deve ser ≥ KM atual.")
        if kr is not None and kr < ka:
            self.add_error("km_prox_revisao", "Deve ser ≥ KM atual.")
        return data


class ObservacoesViaturaForm(forms.ModelForm):
    class Meta:
        model = Viatura
        fields = ["observacoes"]
        widgets = {
            "observacoes": forms.Textarea(attrs={
                "rows": 10,
                "class": "w-full border rounded p-2 text-sm",
                "placeholder": "Registre aqui histórico, problemas, anotações de manutenção, etc."
            })
        }
        labels = {"observacoes": "Observações da Viatura"}


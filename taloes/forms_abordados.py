from __future__ import annotations

from django import forms
from .models import Abordado


class AbordadoForm(forms.ModelForm):
    """
    Formulário para adicionar pessoa ou veículo abordado.
    """
    class Meta:
        model = Abordado
        fields = ["tipo", "nome", "documento", "placa", "modelo", "cor", "observacoes"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "border rounded px-2 py-1"}),
            "nome": forms.TextInput(attrs={"class": "border rounded px-2 py-1 w-full", "placeholder": "Nome completo"}),
            "documento": forms.TextInput(attrs={"class": "border rounded px-2 py-1", "placeholder": "RG/CPF"}),
            "placa": forms.TextInput(attrs={"class": "border rounded px-2 py-1", "placeholder": "ABC-1234"}),
            "modelo": forms.TextInput(attrs={"class": "border rounded px-2 py-1", "placeholder": "Marca/Modelo"}),
            "cor": forms.TextInput(attrs={"class": "border rounded px-2 py-1", "placeholder": "Cor"}),
            "observacoes": forms.Textarea(attrs={"class": "border rounded px-2 py-1 w-full", "rows": 2, "placeholder": "Observações..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Não obrigatório nenhum campo específico por enquanto
        for field in self.fields.values():
            field.required = False
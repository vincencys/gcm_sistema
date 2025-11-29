from django import forms
from .models import Assistida

class AssistidaForm(forms.ModelForm):
    rua = forms.CharField(
        max_length=200,
        required=True,
        label='Rua/Avenida',
        widget=forms.TextInput(attrs={
            'class': 'border rounded px-2 py-1 w-full',
            'placeholder': 'Nome da rua ou avenida'
        })
    )
    numero = forms.CharField(
        max_length=20,
        required=True,
        label='Número',
        widget=forms.TextInput(attrs={
            'class': 'border rounded px-2 py-1 w-full',
            'placeholder': 'Número'
        })
    )
    bairro = forms.CharField(
        max_length=100,
        required=True,
        label='Bairro',
        widget=forms.TextInput(attrs={
            'class': 'border rounded px-2 py-1 w-full',
            'placeholder': 'Bairro'
        })
    )
    referencia = forms.CharField(
        max_length=200,
        required=False,
        label='Referência (opcional)',
        widget=forms.TextInput(attrs={
            'class': 'border rounded px-2 py-1 w-full',
            'placeholder': 'Ponto de referência'
        })
    )

    class Meta:
        model = Assistida
        fields = ['nome', 'cpf', 'telefone', 'processo_mp', 'documento_mp']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'border rounded px-2 py-1 w-full',
                'required': True
            }),
            'cpf': forms.TextInput(attrs={
                'class': 'border rounded px-2 py-1 w-full',
                'required': True,
                'placeholder': '000.000.000-00',
                'maxlength': '14',
                'data-mask': 'cpf'
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'border rounded px-2 py-1 w-full',
                'required': True,
                'placeholder': '(00) 00000-0000',
                'maxlength': '15',
                'data-mask': 'telefone'
            }),
            'processo_mp': forms.TextInput(attrs={
                'class': 'border rounded px-2 py-1 w-full',
                'required': True,
                'placeholder': '0000000-00.0000.0.00.0000',
                'maxlength': '25',
                'data-mask': 'processo'
            }),
            'documento_mp': forms.FileInput(attrs={
                'class': 'border rounded px-2 py-1 w-full',
                'required': True,
                'accept': 'application/pdf,image/*'
            }),
        }
        labels = {
            'nome': 'Nome Completo',
            'cpf': 'CPF',
            'telefone': 'Telefone',
            'processo_mp': 'Número do Processo MP',
            'documento_mp': 'Medida Protetiva (PDF/Imagem)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Se estamos editando, dividir o endereço
        if self.instance.pk and self.instance.endereco:
            partes = self.instance.endereco.split(' | ')
            if len(partes) >= 3:
                self.fields['rua'].initial = partes[0].strip()
                self.fields['numero'].initial = partes[1].strip()
                self.fields['bairro'].initial = partes[2].strip()
                if len(partes) >= 4:
                    self.fields['referencia'].initial = partes[3].strip()

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Montar endereço completo
        rua = self.cleaned_data.get('rua', '').strip()
        numero = self.cleaned_data.get('numero', '').strip()
        bairro = self.cleaned_data.get('bairro', '').strip()
        referencia = self.cleaned_data.get('referencia', '').strip()
        
        endereco_parts = [rua, numero, bairro]
        if referencia:
            endereco_parts.append(referencia)
        instance.endereco = ' | '.join(endereco_parts)
        
        if commit:
            instance.save()
        return instance

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from viaturas.models import Viatura
from .models import Talao, ChecklistViatura, Abastecimento, AitRegistro


# ======================
#   SETUP DO PLANTÃO
# ======================

class SetupPlantaoForm(forms.Form):
    """
    Tela de configuração do plantão (viatura + equipe + texto do plantão).
    Os nomes dos campos batem com o que o views_extra._build_equipe_texto usa.
    """
    viatura = forms.ModelChoiceField(
        queryset=Viatura.objects.all(), required=True, label="Viatura",
        widget=forms.Select(attrs={"class": "js-choices"}),
    )
    plantao = forms.CharField(required=False, label="Plantão")

    # Nomes digitados/livres (não precisam ser usuários do sistema)
    encarregado = forms.CharField(required=False, label="Encarregado")
    motorista = forms.CharField(required=False, label="Motorista")
    auxiliar1 = forms.CharField(required=False, label="Auxiliar 1")
    auxiliar2 = forms.CharField(required=False, label="Auxiliar 2")


class RelatorioRondaForm(forms.Form):
    texto = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 8, "placeholder": "Rascunho do relatório de ronda..."}),
        label="Relatório de Ronda",
    )


# ======================
#   TALÃO
# ======================

User = get_user_model()

def _gcm_queryset():
    try:
        return User.objects.filter(is_active=True, perfil__ativo=True).order_by("username")
    except Exception:
        return User.objects.filter(is_active=True).order_by("username")


class UserNameChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        username = getattr(obj, 'username', '') or ''
        try:
            full = (obj.get_full_name() or '').strip()
        except Exception:
            full = ''
        if full:
            return f"{username} - {full.title()}"
        return username or str(getattr(obj, 'pk', ''))


class MatriculaNomeChoiceField(forms.ModelChoiceField):
    """Exibe 'matrícula - Nome' quando houver perfil.matricula; fallback para username - Nome."""
    def label_from_instance(self, obj):
        try:
            mat = getattr(getattr(obj, 'perfil', None), 'matricula', '') or ''
        except Exception:
            mat = ''
        username = getattr(obj, 'username', '') or ''
        try:
            full = (obj.get_full_name() or '').strip()
        except Exception:
            full = ''
        left = mat or username or str(getattr(obj, 'pk', ''))
        if full:
            return f"{left} - {full.title()}"
        return left


class PlantaoEquipeForm(forms.Form):
    """Form para iniciar plantão escolhendo viatura e até 4 GCMs."""
    viatura = forms.ModelChoiceField(
        queryset=Viatura.objects.all(), required=True, label="Viatura",
        widget=forms.Select(attrs={"class": "js-choices"}),
    )
    plantao = forms.ChoiceField(
        choices=[("", "—"), ("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
        required=False,
        label="Equipe",
        widget=forms.Select(attrs={"class": "js-choices"}),
    )
    coordenador_lider = MatriculaNomeChoiceField(
        queryset=_gcm_queryset(), required=False, label="Coordenador / Líder",
        widget=forms.Select(attrs={"class": "js-choices"}),
    )
    encarregado = UserNameChoiceField(
        queryset=_gcm_queryset(), required=False, label="Encarregado",
        widget=forms.Select(attrs={"class": "js-choices"}),
    )
    motorista = UserNameChoiceField(
        queryset=_gcm_queryset(), required=False, label="Motorista",
        widget=forms.Select(attrs={"class": "js-choices"}),
    )
    auxiliar1 = UserNameChoiceField(
        queryset=_gcm_queryset(), required=False, label="Auxiliar 1",
        widget=forms.Select(attrs={"class": "js-choices"}),
    )
    auxiliar2 = UserNameChoiceField(
        queryset=_gcm_queryset(), required=False, label="Auxiliar 2",
        widget=forms.Select(attrs={"class": "js-choices"}),
    )

    def clean(self):
        data = super().clean()
        # Evitar usuários duplicados nas funções
        ids = [
            getattr(data.get("encarregado"), "id", None),
            getattr(data.get("motorista"), "id", None),
            getattr(data.get("auxiliar1"), "id", None),
            getattr(data.get("auxiliar2"), "id", None),
        ]
        ids = [i for i in ids if i]
        if len(ids) != len(set(ids)):
            raise forms.ValidationError("Não repita o mesmo GCM em funções diferentes.")
        # Observação: o Coordenador/Líder pode coincidir com o Encarregado ou outras funções
        # por orientação do usuário. Por isso não participa da validação de duplicidade acima.
        return data

class NovoTalaoForm(forms.ModelForm):
    class Meta:
        model = Talao
        fields = ("viatura", "km_inicial", "km_final", "codigo_ocorrencia", "local_bairro", "local_rua")
        widgets = {
            "viatura": forms.Select(attrs={"class": "js-choices"}),
            "local_bairro": forms.TextInput(attrs={"placeholder": "Área/Bairro"}),
            "local_rua": forms.TextInput(attrs={"placeholder": "Rua/Refêrencia"}),
            "codigo_ocorrencia": forms.Select(attrs={"class": "js-choices"}),
            "km_final": forms.NumberInput(attrs={"placeholder": "KM Final"}),
        }

    def __init__(self, *args, **kwargs):
        plantao_ativo = kwargs.pop('plantao_ativo', None)
        super().__init__(*args, **kwargs)
        # Se houver plantão ativo, trava a viatura
        if plantao_ativo and hasattr(plantao_ativo, 'viatura_id') and plantao_ativo.viatura_id:
            self.fields['viatura'].disabled = True
            self.fields['viatura'].widget.attrs['class'] = 'js-choices bg-slate-100 cursor-not-allowed'
            self.fields['viatura'].help_text = 'Viatura definida pelo plantão ativo'

    def clean_km_inicial(self):
        v = self.cleaned_data.get("km_inicial")
        if v is None:
            raise forms.ValidationError("Informe o KM inicial.")
        if v < 0:
            raise forms.ValidationError("KM inicial inválido.")
        return v


class TalaoOcorrenciaForm(forms.ModelForm):
    class Meta:
        model = Talao
        fields = ("codigo_ocorrencia", "local_bairro", "local_rua")
        widgets = {
            "local_bairro": forms.TextInput(attrs={"placeholder": "Área/Bairro"}),
            "local_rua": forms.TextInput(attrs={"placeholder": "Rua/Refêrencia"}),
        }


class FinalizarTalaoForm(forms.ModelForm):
    class Meta:
        model = Talao
        fields = ("km_final",)

    def clean_km_final(self):
        kmf = self.cleaned_data.get("km_final")
        if kmf is None:
            raise forms.ValidationError("Informe o KM final para concluir.")
        if kmf < 0:
            raise forms.ValidationError("KM final inválido.")
        return kmf


class LinhaTalaoForm(forms.ModelForm):
    """Usado na lista para edição inline de status/km_final."""
    class Meta:
        model = Talao
        fields = ("status", "km_final")
        widgets = {
            "km_final": forms.NumberInput(attrs={"style": "width: 6rem;"}),
        }


class ChecklistViaturaForm(forms.ModelForm):
    class Meta:
        model = ChecklistViatura
        exclude = ("usuario", "data", "plantao_id", "criado_em", "atualizado_em")
        widgets = {f: forms.CheckboxInput(attrs={'class': 'h-4 w-4'}) for f in [
            'radio_comunicador','sistema_luminoso','bancos','tapetas','painel','limpeza_interna','antena','pneus','calotas','rodas_liga','para_brisa','palhetas_dianteiras','palheta_traseira','farois_dianteiros','farois_neblina','lanternas_traseiras','luz_re','sensor_estacionamento','portinhola_tanque','fluido_freio','liquido_arrefecimento','fluido_direcao','bateria','amortecedor','tampa_porta_malas','estepe','triangulo','chave_rodas','macaco','suspensao','documentacao','oleo'
        ]}
        widgets.update({
            'outros': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descreva outras avarias (opcional)', 'class': 'col-span-full w-full'})
        })


class AbastecimentoForm(forms.ModelForm):
    class Meta:
        model = Abastecimento
        fields = ("requisicao_numero", "tipo_combustivel", "litros", "recibo_do_posto")
        widgets = {
            "requisicao_numero": forms.TextInput(attrs={
                "placeholder": "Nº da Requisição",
                "class": "w-full",
                "inputmode": "numeric",
                "autocomplete": "off",
            }),
            "tipo_combustivel": forms.Select(attrs={
                "class": "w-full",
            }),
            "litros": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "placeholder": "Litros",
                "class": "w-full",
                "inputmode": "decimal",
            }),
            "recibo_do_posto": forms.ClearableFileInput(attrs={
                "class": "w-full",
                "accept": "image/*,application/pdf",
                "capture": "environment",
            }),
        }

    def clean_litros(self):
        v = self.cleaned_data.get("litros")
        if v is None or v <= 0:
            raise forms.ValidationError("Informe a quantidade de litros (maior que zero).")
        return v


class AitAddForm(forms.Form):
    integrante = MatriculaNomeChoiceField(
        queryset=_gcm_queryset(), required=True, label="Integrante",
        widget=forms.Select(attrs={"class": "js-choices w-full"}),
    )
    numero = forms.CharField(
        label="Número da AIT",
        max_length=50,
        widget=forms.TextInput(attrs={
            "placeholder": "Digite o número da AIT e clique em Adicionar",
            "autocomplete": "off",
            "inputmode": "numeric",
            "class": "w-full",
        })
    )


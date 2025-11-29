from django import forms
from django.core.exceptions import ValidationError
import re
from .models import BO, Envolvido, Apreensao, AnexoApreensao, VeiculoEnvolvido, AnexoVeiculo, EquipeApoio

def _cpf_digits(v: str) -> str:
    return ''.join([c for c in (v or '') if c.isdigit()])

def _cpf_is_valid(cpf: str) -> bool:
    d = _cpf_digits(cpf)
    if len(d) != 11:
        return False
    if d == d[0] * 11:
        return False
    try:
        nums = [int(x) for x in d]
    except Exception:
        return False
    # Primeiro dígito
    s = sum(a*b for a,b in zip(nums[:9], range(10,1,-1)))
    r = (s * 10) % 11
    if r == 10:
        r = 0
    if nums[9] != r:
        return False
    # Segundo dígito
    s = sum(a*b for a,b in zip(nums[:10], range(11,1,-1)))
    r = (s * 10) % 11
    if r == 10:
        r = 0
    return nums[10] == r

def _cnpj_digits(v: str) -> str:
    return ''.join([c for c in (v or '') if c.isdigit()])

def _cnpj_is_valid(cnpj: str) -> bool:
    d = _cnpj_digits(cnpj)
    if len(d) != 14:
        return False
    if d == d[0] * 14:
        return False
    try:
        nums = [int(x) for x in d]
    except Exception:
        return False
    def dv(nums_in, pesos):
        s = sum(n*p for n,p in zip(nums_in, pesos))
        r = s % 11
        return 0 if r < 2 else 11 - r
    dv1 = dv(nums[:12], [5,4,3,2,9,8,7,6,5,4,3,2])
    if nums[12] != dv1:
        return False
    dv2 = dv(nums[:13], [6,5,4,3,2,9,8,7,6,5,4,3,2])
    return nums[13] == dv2

_PLACA_OLD = re.compile(r"^[A-Z]{3}-\d{4}$")
_PLACA_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")

def _placa_is_valid(placa: str) -> bool:
    if not placa:
        return False
    p = (placa or '').strip().upper()
    return bool(_PLACA_OLD.match(p) or _PLACA_MERCOSUL.match(p))

class BOForm(forms.ModelForm):
    class Meta:
        model = BO
        fields = ['emissao','natureza','cod_natureza','solicitante','endereco','bairro','viatura','motorista','envolvidos','providencias']
        widgets = {
            'emissao': forms.DateTimeInput(attrs={'type':'datetime-local'}),
            'envolvidos': forms.Textarea(attrs={'rows':3}),
            'providencias': forms.Textarea(attrs={'rows':3}),
        }

class EnvolvidoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Se já há assinatura, bloquear edição de dados_adicionais no formulário
        try:
            inst = getattr(self, 'instance', None)
            if inst and getattr(inst, 'pk', None) and getattr(inst, 'assinatura', None):
                if 'dados_adicionais' in self.fields:
                    self.fields['dados_adicionais'].disabled = True
                    self.fields['dados_adicionais'].required = False
        except Exception:
            # Não interromper o fluxo do form em caso de qualquer erro aqui
            pass

    def clean_dados_adicionais(self):
        """Ignora qualquer tentativa de alteração quando já existe assinatura.

        Política: manter valor original silenciosamente (sem erro de validação)
        para evitar bloqueios no fluxo de edição do restante dos campos.
        """
        inst = getattr(self, 'instance', None)
        try:
            if inst and getattr(inst, 'pk', None) and getattr(inst, 'assinatura', None):
                return inst.dados_adicionais
        except Exception:
            # Em caso de qualquer problema, retorna o valor submetido
            pass
        return self.cleaned_data.get('dados_adicionais', '')

    def clean_cpf(self):
        cpf = (self.cleaned_data.get('cpf') or '').strip()
        if not cpf:
            return cpf
        if not _cpf_is_valid(cpf):
            raise ValidationError('CPF inválido (dígitos verificadores não conferem).')
        return cpf

    class Meta:
        model = Envolvido
        fields = '__all__'
        widgets = {
            'anexo': forms.ClearableFileInput(attrs={'multiple': False}),
        }

class ApreensaoForm(forms.ModelForm):
    class Meta:
        model = Apreensao
        fields = ['descricao', 'unidade_medida', 'quantidade', 'destino', 'recebedor']

class AnexoApreensaoForm(forms.ModelForm):
    class Meta:
        model = AnexoApreensao
        fields = ['descricao', 'arquivo']

class VeiculoEnvolvidoForm(forms.ModelForm):
    class Meta:
        model = VeiculoEnvolvido
        fields = [
            'marca', 'modelo', 'placa', 'renavam', 'numero_chassi', 'numero_motor', 'placa_cidade', 'placa_estado', 'cor', 'ano_modelo', 'ano_fabricacao',
            'semaforo', 'tipo_pista', 'tipo_acidente', 'tempo', 'iluminacao',
            'proprietario', 'cpf', 'cnpj', 'cnh', 'categoria_cnh', 'validade_cnh',
            'situacao_veiculo', 'observacao_situacao', 'danos_identificados',
            # Novos campos de Apreensão
            'apreensao_ait', 'apreensao_crr', 'apreensao_responsavel_guincho', 'apreensao_destino'
        ]
        widgets = {
            'observacao_situacao': forms.Textarea(attrs={'rows': 4}),
            'placa_estado': forms.TextInput(attrs={'maxlength': 2}),
            'ano_modelo': forms.TextInput(attrs={'maxlength': 4}),
            'ano_fabricacao': forms.TextInput(attrs={'maxlength': 4}),
            'validade_cnh': forms.DateInput(attrs={'type': 'date'}),
            'apreensao_ait': forms.TextInput(attrs={'placeholder': "n° das AIT's relacionadas"}),
            'apreensao_crr': forms.TextInput(attrs={'placeholder': 'n° do CRR'}),
            'apreensao_responsavel_guincho': forms.TextInput(attrs={'placeholder': 'Responsável pelo Guincho'}),
            'apreensao_destino': forms.TextInput(attrs={'placeholder': 'Destino'}),
        }

    def clean_cpf(self):
        cpf = (self.cleaned_data.get('cpf') or '').strip()
        if not cpf:
            return cpf
        if not _cpf_is_valid(cpf):
            raise ValidationError('CPF inválido. Verifique os dígitos.')
        return cpf

    def clean_cnpj(self):
        cnpj = (self.cleaned_data.get('cnpj') or '').strip()
        if not cnpj:
            return cnpj
        if not _cnpj_is_valid(cnpj):
            raise ValidationError('CNPJ inválido. Verifique os dígitos.')
        return cnpj

    def clean_placa(self):
        placa = (self.cleaned_data.get('placa') or '').strip().upper()
        if not placa:
            return placa
        # Normaliza formato antigo se possível (AAA9999 -> AAA-9999)
        raw = re.sub(r"[^A-Z0-9]", "", placa)
        if len(raw) == 7 and raw[:3].isalpha() and raw[3:].isdigit():
            placa_norm = f"{raw[:3]}-{raw[3:]}"
        else:
            placa_norm = placa
        if not _placa_is_valid(placa_norm):
            raise ValidationError('Placa inválida. Formatos aceitos: AAA-9999 (antigo) ou ABC1D23 (Mercosul).')
        return placa_norm

class AnexoVeiculoForm(forms.ModelForm):
    class Meta:
        model = AnexoVeiculo
        fields = ['descricao', 'arquivo']

class EquipeApoioForm(forms.ModelForm):
    class Meta:
        model = EquipeApoio
        fields = ['viatura', 'instituicao', 'participantes', 'observacoes']
        widgets = {
            'participantes': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Ex: GCM João Silva - 12345, PM Carlos Santos - 67890, etc.'}),
            'observacoes': forms.Textarea(attrs={'rows': 4}),
        }

from django import forms
from django.contrib.auth import get_user_model
from users.models import Perfil
from .models import Dispensa, NotificacaoFiscalizacao, AutoInfracaoComercio, AutoInfracaoSom, OficioInterno
from django.core.files.base import ContentFile
import base64

User = get_user_model()


class UserMatriculaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        perfil = getattr(obj, "perfil", None)
        nome = obj.get_full_name() or obj.get_username()
        matricula = getattr(perfil, "matricula", "") or obj.get_username()
        return f"{matricula} - {nome}"


class DispensaSolicitacaoForm(forms.ModelForm):
    supervisor = UserMatriculaChoiceField(queryset=User.objects.none(), required=True, label="Supervisor",
                                          widget=forms.Select(attrs={"class": "w-full border rounded p-2"}))

    class Meta:
        model = Dispensa
        fields = ["plantao", "data", "tipo", "turno", "supervisor", "observacao"]
        widgets = {
            "plantao": forms.Select(attrs={"class": "w-full border rounded p-2"}),
            "data": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "w-full border rounded p-2"}),
            "tipo": forms.Select(attrs={"class": "w-full border rounded p-2"}),
            "turno": forms.Select(attrs={"class": "w-full border rounded p-2"}),
            "observacao": forms.Textarea(attrs={"rows": 3, "class": "w-full border rounded p-2"}),
        }
        labels = {
            "observacao": "Observação/Motivo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Usuários com perfil (matrícula), ativos
        self.fields["supervisor"].queryset = (
            User.objects.select_related("perfil")
            .filter(is_active=True, perfil__isnull=False)
            .order_by("perfil__matricula", "username")
        )


class DispensaAprovacaoForm(forms.Form):
    acao = forms.ChoiceField(
        choices=(
            ("aprovar", "Aprovar"),
            ("recusar", "Recusar"),
        ),
        widget=forms.RadioSelect,
    )
    mensagem = forms.CharField(
        label="Mensagem (se recusar)", required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "w-full"})
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("acao") == "recusar" and not (cleaned.get("mensagem") or "").strip():
            self.add_error("mensagem", "Informe o motivo da recusa.")
        return cleaned


# --------------------- Fiscalização: Notificações ---------------------
class NotificacaoFiscalizacaoForm(forms.ModelForm):
    assinatura_dataurl = forms.CharField(widget=forms.HiddenInput(), required=False)
    enviar_segunda_via = forms.BooleanField(label='Enviar segunda via por e-mail', required=False)

    class Meta:
        model = NotificacaoFiscalizacao
        fields = [
            'notificado_nome', 'notificado_email', 'notificado_cpf', 'notificado_cnpj', 'endereco', 'bairro', 'cidade', 'atividade_ramo',
            'referente', 'prazo_dias', 'prazo_horas', 'observacoes',
            'data_recebimento', 'fiscal_matricula',
            'recusou_assinar', 'assinatura_notificado'
        ]
        widgets = {
              'notificado_nome': forms.TextInput(attrs={'class': 'input w-full'}),
              'notificado_email': forms.EmailInput(attrs={'class': 'input w-full'}),
              'notificado_cpf': forms.TextInput(attrs={'class': 'input w-full'}),
              'notificado_cnpj': forms.TextInput(attrs={'class': 'input w-full'}),
              'endereco': forms.TextInput(attrs={'class': 'input w-full'}),
              'bairro': forms.TextInput(attrs={'class': 'input w-full'}),
              'cidade': forms.TextInput(attrs={'class': 'input w-full'}),
              'atividade_ramo': forms.TextInput(attrs={'class': 'input w-full'}),
              'referente': forms.Textarea(attrs={'rows':3, 'class':'input w-full'}),
              'prazo_dias': forms.NumberInput(attrs={'class': 'input w-full'}),
              'prazo_horas': forms.NumberInput(attrs={'class': 'input w-full'}),
              'observacoes': forms.Textarea(attrs={'rows':3, 'class':'input w-full'}),
              'data_recebimento': forms.DateInput(format='%Y-%m-%d', attrs={'type':'date', 'class':'input w-full'}),
              'fiscal_matricula': forms.TextInput(attrs={'class': 'input w-full'}),
              'recusou_assinar': forms.CheckboxInput(attrs={'class': 'input'}),
              'assinatura_notificado': forms.ClearableFileInput(attrs={'class': 'input w-full'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Renomeia o rótulo para Data de Elaboração e preenche com a data atual por padrão
        if 'data_recebimento' in self.fields:
            self.fields['data_recebimento'].label = 'Data de Elaboração'
            if not self.instance.pk and not (self.data and self.add_prefix('data_recebimento') in self.data):
                from django.utils import timezone
                self.fields['data_recebimento'].initial = timezone.localdate()

    def clean_notificado_cpf(self):
        v = (self.cleaned_data.get('notificado_cpf') or '').strip()
        if not v:
            return v
        import re
        digits = re.sub(r'\D+', '', v)
        if len(digits) != 11:
            raise forms.ValidationError('CPF deve ter 11 dígitos.')
        return digits

    def clean_notificado_cnpj(self):
        v = (self.cleaned_data.get('notificado_cnpj') or '').strip()
        if not v:
            return v
        import re
        digits = re.sub(r'\D+', '', v)
        if len(digits) != 14:
            raise forms.ValidationError('CNPJ deve ter 14 dígitos.')
        return digits

    def clean(self):
        cleaned = super().clean()
        recusou = cleaned.get('recusou_assinar')
        assin = cleaned.get('assinatura_notificado')
        dataurl = self.data.get(self.add_prefix('assinatura_dataurl')) or ''
        if not recusou:
            if not assin and not (dataurl and dataurl.startswith('data:image')):
                self.add_error('assinatura_notificado', 'Obrigatória a assinatura do notificado ou marcar recusa.')
        return cleaned

    def save(self, commit=True, user=None):
        obj = super().save(commit=False)
        # Fiscal responsável padrão = usuário atual, se fornecido
        if user is not None and not obj.fiscal_responsavel_id:
            obj.fiscal_responsavel = user
        # Tratar assinatura via dataurl
        dataurl = self.data.get(self.add_prefix('assinatura_dataurl')) or ''
        recusou = self.cleaned_data.get('recusou_assinar')
        if recusou:
            # limpar assinatura
            obj.assinatura_notificado = None
        else:
            if dataurl.startswith('data:image'):
                try:
                    header, b64 = dataurl.split(',', 1)
                    bin_data = base64.b64decode(b64)
                    obj.assinatura_notificado = ContentFile(bin_data, name='assinatura.png')
                except Exception:
                    pass
        if commit:
            obj.save()
        return obj


# --------------------- Fiscalização: Autos de Infração ---------------------
class _AssinaturaMixin:

    def clean(self):
        cleaned = super().clean()
        recusou = cleaned.get('recusou_assinar')
        assin = cleaned.get('assinatura_notificado')
        dataurl = self.data.get(self.add_prefix('assinatura_dataurl')) or ''
        if not recusou:
            if not assin and not (dataurl and dataurl.startswith('data:image')):
                self.add_error('assinatura_notificado', 'Obrigatória a assinatura do autuado ou marcar recusa.')
        return cleaned

    def _aplicar_assinatura(self, obj):
        dataurl = self.data.get(self.add_prefix('assinatura_dataurl')) or ''
        recusou = self.cleaned_data.get('recusou_assinar')
        if recusou:
            obj.assinatura_notificado = None
        else:
            if dataurl.startswith('data:image'):
                try:
                    header, b64 = dataurl.split(',', 1)
                    bin_data = base64.b64decode(b64)
                    obj.assinatura_notificado = ContentFile(bin_data, name='assinatura.png')
                except Exception:
                    pass
        return obj


class AutoInfracaoComercioForm(_AssinaturaMixin, forms.ModelForm):
    # Campos auxiliares (não-model) devem ser declarados diretamente na ModelForm
    assinatura_dataurl = forms.CharField(widget=forms.HiddenInput(), required=False)
    enviar_segunda_via = forms.BooleanField(label='Enviar segunda via por e-mail', required=False)
    class Meta:
        model = AutoInfracaoComercio
        fields = [
            'notificado_nome', 'notificado_email', 'notificado_cpf', 'notificado_cnpj',
            'endereco', 'bairro', 'cidade', 'estado_civil', 'profissao_atividade', 'inscricao_municipal',
            'descricao_infracao', 'artigos_infringidos', 'lei_numero', 'lei_data', 'valor_multa',
            'notificacao_entrega', 'prazo_defesa_dias', 'observacoes',
            'fiscal_matricula', 'recusou_assinar', 'assinatura_notificado',
        ]
        widgets = {
              'notificado_nome': forms.TextInput(attrs={'class': 'input w-full'}),
              'notificado_email': forms.EmailInput(attrs={'class': 'input w-full'}),
              'notificado_cpf': forms.TextInput(attrs={'class': 'input w-full'}),
              'notificado_cnpj': forms.TextInput(attrs={'class': 'input w-full'}),
              'endereco': forms.TextInput(attrs={'class': 'input w-full'}),
              'bairro': forms.TextInput(attrs={'class': 'input w-full'}),
              'cidade': forms.TextInput(attrs={'class': 'input w-full'}),
              'estado_civil': forms.Select(attrs={'class': 'input w-full'}),
              'profissao_atividade': forms.TextInput(attrs={'class': 'input w-full'}),
              'inscricao_municipal': forms.TextInput(attrs={'class': 'input w-full'}),
              'descricao_infracao': forms.Textarea(attrs={'rows':3, 'class':'input w-full'}),
              'artigos_infringidos': forms.TextInput(attrs={'class': 'input w-full'}),
              'lei_numero': forms.TextInput(attrs={'class': 'input w-full'}),
              'lei_data': forms.DateInput(format='%Y-%m-%d', attrs={'type':'date', 'class':'input w-full'}),
              'valor_multa': forms.NumberInput(attrs={'class': 'input w-full'}),
              'notificacao_entrega': forms.CheckboxInput(attrs={'class': 'input'}),
              'prazo_defesa_dias': forms.NumberInput(attrs={'class': 'input w-full'}),
              'observacoes': forms.Textarea(attrs={'rows':3, 'class':'input w-full'}),
              'fiscal_matricula': forms.TextInput(attrs={'class': 'input w-full'}),
              'recusou_assinar': forms.CheckboxInput(attrs={'class': 'input'}),
              'assinatura_notificado': forms.ClearableFileInput(attrs={'class': 'input w-full'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Preencher máscara de CPF/CNPJ no front (feito no template)

    def clean_notificado_cpf(self):
        v = (self.cleaned_data.get('notificado_cpf') or '').strip()
        if not v:
            return v
        import re
        digits = re.sub(r'\D+', '', v)
        if len(digits) != 11:
            raise forms.ValidationError('CPF deve ter 11 dígitos.')
        return digits

    def clean_notificado_cnpj(self):
        v = (self.cleaned_data.get('notificado_cnpj') or '').strip()
        if not v:
            return v
        import re
        digits = re.sub(r'\D+', '', v)
        if len(digits) != 14:
            raise forms.ValidationError('CNPJ deve ter 14 dígitos.')
        return digits

    def save(self, commit=True, user=None):
        obj = super().save(commit=False)
        if user is not None and not obj.fiscal_responsavel_id:
            obj.fiscal_responsavel = user
        obj = self._aplicar_assinatura(obj)
        if commit:
            obj.save()
        return obj


SOM_BASE_LEGAL_TEXT = (
    "Infração ao Artigo 3º da Lei nº 1.890 de 16 de Outubro de 2013, "
    "regulamentada pelo Decreto nº 3.105 de 15 de Fevereiro de 2023."
)


class AutoInfracaoSomForm(_AssinaturaMixin, forms.ModelForm):
    # Campos auxiliares (não-model) devem ser declarados diretamente na ModelForm
    assinatura_dataurl = forms.CharField(widget=forms.HiddenInput(), required=False)
    enviar_segunda_via = forms.BooleanField(label='Enviar segunda via por e-mail', required=False)
    class Meta:
        model = AutoInfracaoSom
        fields = [
            'notificado_nome', 'notificado_email', 'notificado_cpf', 'notificado_cnpj',
            'endereco', 'referencia', 'ponto',
            'valor_medido_db', 'permitido_db', 'periodo', 'reincidencia',
            'classificacao', 'observacoes',
            'fiscal_matricula', 'recusou_assinar', 'assinatura_notificado',
        ]
        widgets = {
              'notificado_nome': forms.TextInput(attrs={'class': 'input w-full'}),
              'notificado_email': forms.EmailInput(attrs={'class': 'input w-full'}),
              'notificado_cpf': forms.TextInput(attrs={'class': 'input w-full'}),
              'notificado_cnpj': forms.TextInput(attrs={'class': 'input w-full'}),
              'endereco': forms.TextInput(attrs={'class': 'input w-full'}),
              'referencia': forms.TextInput(attrs={'class': 'input w-full'}),
              'ponto': forms.TextInput(attrs={'class': 'input w-full'}),
              'valor_medido_db': forms.NumberInput(attrs={'class': 'input w-full'}),
              'permitido_db': forms.NumberInput(attrs={'class': 'input w-full'}),
              'periodo': forms.TextInput(attrs={'class': 'input w-full'}),
              'reincidencia': forms.CheckboxInput(attrs={'class': 'input'}),
              'classificacao': forms.TextInput(attrs={'class': 'input w-full'}),
              'observacoes': forms.Textarea(attrs={'rows':3, 'class':'input w-full'}),
              'fiscal_matricula': forms.TextInput(attrs={'class': 'input w-full'}),
              'recusou_assinar': forms.CheckboxInput(attrs={'class': 'input'}),
              'assinatura_notificado': forms.ClearableFileInput(attrs={'class': 'input w-full'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_notificado_cpf(self):
        v = (self.cleaned_data.get('notificado_cpf') or '').strip()
        if not v:
            return v
        import re
        digits = re.sub(r'\D+', '', v)
        if len(digits) != 11:
            raise forms.ValidationError('CPF deve ter 11 dígitos.')
        return digits

    def clean_notificado_cnpj(self):
        v = (self.cleaned_data.get('notificado_cnpj') or '').strip()
        if not v:
            return v
        import re
        digits = re.sub(r'\D+', '', v)
        if len(digits) != 14:
            raise forms.ValidationError('CNPJ deve ter 14 dígitos.')
        return digits

    def save(self, commit=True, user=None):
        obj = super().save(commit=False)
        if user is not None and not obj.fiscal_responsavel_id:
            obj.fiscal_responsavel = user
        # Base Legal fixa (não editável pelo usuário)
        obj.base_legal = SOM_BASE_LEGAL_TEXT
        obj = self._aplicar_assinatura(obj)
        if commit:
            obj.save()
        return obj


# --------------------- Administração: Ofício Interno ---------------------
class OficioInternoForm(forms.ModelForm):
    supervisor = UserMatriculaChoiceField(queryset=User.objects.none(), required=True, label="Supervisor")

    class Meta:
        model = OficioInterno
        fields = ["supervisor", "tipo", "texto"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "w-full"}),
            "texto": forms.Textarea(attrs={"rows": 6, "class": "w-full"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supervisor"].queryset = (
            User.objects.select_related("perfil").filter(is_active=True, perfil__isnull=False).order_by("perfil__matricula", "username")
        )

    def save(self, commit=True, user=None):
        obj: OficioInterno = super().save(commit=False)
        if user is not None and not obj.criador_id:
            obj.criador = user
        # status inicial e responsável atual
        if not obj.pk:
            obj.status = "PEND_SUP"
            obj.responsavel_atual = obj.supervisor
        if commit:
            obj.save()
        return obj

class OficioAcaoForm(forms.Form):
    acao = forms.ChoiceField(choices=(
        ("DEFERIR", "Deferir"),
        ("INDEFERIR", "Indeferir"),
        ("DESP_SUB", "Despachar para SUBCMT"),
        ("DESP_CMT", "Despachar para CMT"),
    ))
    observacao = forms.CharField(widget=forms.Textarea(attrs={"rows":3, "class":"w-full"}), required=False)

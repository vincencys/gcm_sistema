from django import forms
from .models import DespachoOcorrencia, PlantaoCecomPrincipal, LivroPlantaoCecom, LivroPlantaoCecomViatura, LivroPlantaoCecomPostoFixo
from django.contrib.auth import get_user_model
User = get_user_model()


def _fmt_user_label(u):
    perfil = getattr(u, 'perfil', None)
    matricula = ''
    if perfil:
        matricula = getattr(perfil, 'matricula', '')
    if not matricula:
        matricula = u.username
    nome = (u.get_full_name() or u.username).strip()
    # Exibe em uma linha, com espaço entre matrícula e nome
    return f"{matricula} - {nome}" if nome else matricula
from viaturas.models import Viatura


class DespachoOcorrenciaForm(forms.ModelForm):
    codigo = forms.ChoiceField(
        label='Código da Ocorrência', required=False,
        widget=forms.Select(attrs={'class': 'w-full border rounded px-3 py-2 js-choices'})
    )
    class Meta:
        model = DespachoOcorrencia
        fields = ['viatura', 'endereco', 'nome_solicitante', 'telefone_solicitante', 'descricao', 'latitude', 'longitude']
        widgets = {
            'viatura': forms.Select(attrs={'class': 'w-full border rounded px-3 py-2'}),
            'endereco': forms.TextInput(attrs={
                'class': 'w-full border rounded px-3 py-2',
                'placeholder': 'Digite o endereço completo...',
                'id': 'endereco-input'
            }),
            'nome_solicitante': forms.TextInput(attrs={
                'class': 'w-full border rounded px-3 py-2',
                'placeholder': 'Nome do solicitante (opcional)'
            }),
            'telefone_solicitante': forms.TextInput(attrs={
                'class': 'w-full border rounded px-3 py-2',
                'placeholder': '(11) 99999-9999'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'w-full border rounded px-3 py-2',
                'rows': 4,
                'placeholder': 'Descreva a ocorrência...'
            }),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar apenas viaturas ativas
        self.fields['viatura'].queryset = Viatura.objects.filter(ativo=True)
        # Montar opções de códigos a partir do cadastro mestre (taloes.CodigoOcorrencia)
        try:
            from taloes.models import CodigoOcorrencia  # import interno evita acoplamento em load inicial
            lista = CodigoOcorrencia.objects.all().order_by('sigla').values_list('sigla', 'descricao')
            choices = [('', 'Sem código')] + [(sigla, f"{sigla} — {desc}".strip()) for sigla, desc in lista]
        except Exception:
            choices = [('', 'Sem código')]
        self.fields['codigo'].choices = choices

        # Se já existir valor no instance, pré-selecionar
        inst = getattr(self, 'instance', None)
        if inst and getattr(inst, 'cod_natureza', ''):
            # garantir presença do código atual nos choices
            rotulo = inst.cod_natureza
            if getattr(inst, 'natureza', ''):
                rotulo = f"{inst.cod_natureza} — {inst.natureza}"
            if not any(c[0] == inst.cod_natureza for c in choices):
                self.fields['codigo'].choices = [(inst.cod_natureza, rotulo)] + choices
            self.initial['codigo'] = inst.cod_natureza

    def save(self, commit=True):
        obj: DespachoOcorrencia = super().save(commit=False)
        cod = (self.cleaned_data.get('codigo') or '').strip()
        obj.cod_natureza = cod
        # Buscar descrição no cadastro mestre
        desc = ''
        try:
            from taloes.models import CodigoOcorrencia
            if cod:
                co = CodigoOcorrencia.objects.filter(sigla=cod).values_list('descricao', flat=True).first()
                if co:
                    desc = co
        except Exception:
            # Fallback: extrair de label caso o import não funcione
            try:
                label = dict(self.fields['codigo'].choices).get(cod, '')
                if '—' in label:
                    desc = label.split('—', 1)[1].strip()
                elif ' - ' in label:
                    desc = label.split(' - ', 1)[1].strip()
            except Exception:
                desc = ''
        obj.natureza = desc
        if commit:
            obj.save()
        return obj


class PlantaoCecomIniciarForm(forms.ModelForm):
    class Meta:
        model = PlantaoCecomPrincipal
        fields = ['aux_cecom']
        widgets = {
            'aux_cecom': forms.Select(attrs={'class': 'w-full border rounded px-3 py-2 js-choices'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(is_active=True).order_by('username').select_related('perfil')
        f = self.fields['aux_cecom']
        f.queryset = qs
        f.choices = [('', '---------')] + [(u.id, _fmt_user_label(u)) for u in qs]
        # Agora obrigatório selecionar operador (aux_cecom)
        f.required = True
        f.error_messages['required'] = 'Selecione o Operador do CECOM.'
        # Valor padrão: usuário logado (se estiver no queryset)
        if user and user.is_active:
            if qs.filter(id=user.id).exists():
                self.initial.setdefault('aux_cecom', user.id)


class LivroPlantaoCecomForm(forms.ModelForm):
    class Meta:
        model = LivroPlantaoCecom
        fields = [
            'equipe_plantao','cga_do_dia','dispensados','atraso_servico','banco_horas','hora_extra',
            'aits_recebidas','ocorrencias_nao_atendidas','ocorrencias_do_plantao','observacoes',
            'chk_radio','chk_computador','chk_cameras','chk_celulares','chk_carregadores','chk_telefones','chk_livros','chk_monitor'
        ]
        widgets = {
            'equipe_plantao': forms.Select(attrs={'class':'border rounded px-2 py-1'}),
            'cga_do_dia': forms.Select(attrs={'class':'border rounded px-2 py-1 js-choices'}),
            'dispensados': forms.Textarea(attrs={'class':'w-full border rounded p-2','rows':2}),
            'atraso_servico': forms.Textarea(attrs={'class':'w-full border rounded p-2','rows':2}),
            'banco_horas': forms.Textarea(attrs={'class':'w-full border rounded p-2','rows':2}),
            'hora_extra': forms.Textarea(attrs={'class':'w-full border rounded p-2','rows':2}),
            'ocorrencias_nao_atendidas': forms.Textarea(attrs={'class':'w-full border rounded p-2','rows':3}),
            'ocorrencias_do_plantao': forms.Textarea(attrs={'class':'w-full border rounded p-2','rows':3}),
            'observacoes': forms.Textarea(attrs={'class':'w-full border rounded p-2','rows':2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(is_active=True).order_by('username').select_related('perfil')
        f = self.fields['cga_do_dia']
        f.queryset = qs
        f.choices = [('', '---------')] + [(u.id, _fmt_user_label(u)) for u in qs]
        # Não pré-selecionar automaticamente para permanecer no traço por padrão
        # (mantém valor salvo do instance quando existir)
        # Exibir placeholder mesmo quando já existe valor salvo
        if getattr(self.instance, 'cga_do_dia_id', None):
            self.initial['cga_do_dia'] = ''

    def clean(self):
        data = super().clean()
        # Se o usuário deixou o CGA no traço (vazio), manter o valor existente do instance (não limpar)
        if (
            self.instance and getattr(self.instance, 'pk', None)
            and getattr(self.instance, 'cga_do_dia_id', None)
            and data.get('cga_do_dia') is None
        ):
            data['cga_do_dia'] = self.instance.cga_do_dia
        return data


class LivroPlantaoCecomViaturaForm(forms.ModelForm):
    class Meta:
        model = LivroPlantaoCecomViatura
        fields = ['viatura','integrante1','integrante2','integrante3','integrante4']
        widgets = {
            'viatura': forms.Select(attrs={'class':'border rounded px-2 py-1 js-choices'}),
            'integrante1': forms.Select(attrs={'class':'border rounded px-2 py-1 js-choices'}),
            'integrante2': forms.Select(attrs={'class':'border rounded px-2 py-1 js-choices'}),
            'integrante3': forms.Select(attrs={'class':'border rounded px-2 py-1 js-choices'}),
            'integrante4': forms.Select(attrs={'class':'border rounded px-2 py-1 js-choices'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ativos = User.objects.filter(is_active=True).order_by('username').select_related('perfil')
        for fname in ['integrante1','integrante2','integrante3','integrante4']:
            fld = self.fields[fname]
            fld.queryset = ativos
            fld.choices = [('', '---------')] + [(u.id, _fmt_user_label(u)) for u in ativos]
        self.fields['viatura'].queryset = Viatura.objects.filter(ativo=True)


class LivroPlantaoCecomPostoFixoForm(forms.ModelForm):
    class Meta:
        model = LivroPlantaoCecomPostoFixo
        fields = ['tipo','descricao_outros','gcm1','gcm2']
        widgets = {
            'tipo': forms.Select(attrs={'class':'border rounded px-2 py-1 js-choices'}),
            'descricao_outros': forms.TextInput(attrs={'class':'border rounded px-2 py-1','placeholder':'Se OUTROS, descreva'}),
            'gcm1': forms.Select(attrs={'class':'border rounded px-2 py-1 js-choices'}),
            'gcm2': forms.Select(attrs={'class':'border rounded px-2 py-1 js-choices'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ativos = User.objects.filter(is_active=True).order_by('username').select_related('perfil')
        for fname in ['gcm1','gcm2']:
            fld = self.fields[fname]
            fld.queryset = ativos
            fld.choices = [('', '---------')] + [(u.id, _fmt_user_label(u)) for u in ativos]
    def clean(self):
        data = super().clean()
        if data.get('tipo') == 'OUTROS' and not data.get('descricao_outros'):
            self.add_error('descricao_outros','Obrigatório quando tipo é OUTROS.')
        return data
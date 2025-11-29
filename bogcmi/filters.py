import django_filters as df
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import BO

User = get_user_model()

STATUS_CHOICES = (
    ('', '---'),
    ('EDICAO', 'Em edição'),
    ('FINALIZADO', 'Finalizado'),
)

class BOFilter(df.FilterSet):
    emissao_de = df.DateFilter(field_name='emissao', lookup_expr='date__gte', label='Emissão ≥', widget=forms.DateInput(attrs={'type':'date'}))
    emissao_ate = df.DateFilter(field_name='emissao', lookup_expr='date__lte', label='Emissão ≤', widget=forms.DateInput(attrs={'type':'date'}))
    natureza = df.CharFilter(field_name='natureza', lookup_expr='icontains', label='Natureza contém', widget=forms.TextInput(attrs={'placeholder':'Trecho...'}))
    cod_natureza = df.CharFilter(field_name='cod_natureza', lookup_expr='iexact', label='Código de Ocorrência')
    # Busca por número do BO: corresponde precisamente ao número anterior ao hífen (ex.: "2" → "2-2025").
    # Aceita entradas como "2/2025" ou "2-2025" para match exato no campo completo.
    numero = df.CharFilter(method='filter_numero_exato', label='Número', widget=forms.TextInput(attrs={'placeholder':'Ex: 2 ou 2/2025'}))
    status = df.ChoiceFilter(field_name='status', choices=STATUS_CHOICES, empty_label='---', label='Status')
    motorista = df.ModelChoiceFilter(queryset=User.objects.all(), label='Motorista', to_field_name='id', widget=forms.Select())
    encarregado = df.ModelChoiceFilter(queryset=User.objects.all(), label='Encarregado', to_field_name='id', widget=forms.Select())
    envolvido = df.CharFilter(method='filter_envolvido', label='Envolvido', widget=forms.TextInput(attrs={'placeholder':'Nome, CPF ou Vulgo...'}))
    flagrante = df.ChoiceFilter(
        label='Flagrante',
        choices=(('', '---'), ('sim', 'Sim'), ('nao', 'Não')),
        method='filter_flagrante'
    )

    def filter_envolvido(self, queryset, name, value):
        if not value:
            return queryset
        # Busca por nome, cpf ou vulgo nos Envolvidos relacionados ao BO
        return queryset.filter(
            Q(envolvidos_bo__nome__icontains=value) |
            Q(envolvidos_bo__cpf__icontains=value) |
            Q(envolvidos_bo__vulgo__icontains=value)
        ).distinct()

    def filter_flagrante(self, queryset, name, value):
        if not value:
            return queryset
        # Campo "flagrante" é texto livre na base ("Sim"/"Não"), com possibilidade de variações.
        # Regra:
        # - sim: somente registros cujo valor normalizado é "Sim" (ou "S").
        # - nao: registros com "Não"/"Nao"/"N" OU vazios/nulos.
        if value == 'sim':
            return queryset.filter(
                Q(flagrante__iexact='Sim') |
                Q(flagrante__iexact='S')
            )
        if value == 'nao':
            return queryset.filter(
                Q(flagrante__isnull=True) |
                Q(flagrante__exact='') |
                Q(flagrante__iexact='Não') |
                Q(flagrante__iexact='Nao') |
                Q(flagrante__iexact='N')
            )
        return queryset

    def filter_numero_exato(self, queryset, name, value):
        """Filtra por número do BO de forma precisa.
        Casos aceitos:
        - "2" => numero startswith "2-"
        - "2/2025" ou "2-2025" => numero iexact "2-2025"
        - "#2" => tratado como "2"
        """
        if not value:
            return queryset
        v = str(value).strip()
        if v.startswith('#'):
            v = v[1:].strip()
        v = v.replace('/', '-').replace(' ', '')
        if '-' in v and any(ch.isdigit() for ch in v):
            return queryset.filter(numero__iexact=v)
        # somente a parte numérica antes do hífen
        return queryset.filter(numero__istartswith=f"{v}-")

    class Meta:
        model = BO
        # Declaramos apenas filtros automáticos necessários.
        # Os demais filtros já são definidos manualmente acima.
        fields = {
            'viatura': ['exact'],
        }

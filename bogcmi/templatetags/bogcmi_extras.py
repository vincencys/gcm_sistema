from django import template

register = template.Library()
@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except Exception:
        return None

@register.filter
def split_csv(value, sep=','):
    if not value:
        return []
    return [p.strip() for p in str(value).split(sep) if p.strip()]

@register.filter
def humaniza_dano(value):
    if not value:
        return ''
    return str(value).replace('-', ' ')

@register.filter
def descricao_natureza(value):
    """Retorna apenas a parte descritiva após 'SIGLA - ' se nesse formato."""
    if not value:
        return ''
    text = str(value)
    if ' - ' in text:
        return text.split(' - ', 1)[1]
    return text

@register.filter
def extrai_sigla(value):
    """Extrai a sigla antes de ' - ' caso 'cod_natureza' não esteja preenchido."""
    if not value:
        return ''
    text = str(value)
    if ' - ' in text:
        return text.split(' - ', 1)[0]
    return text

@register.filter
def codigo_badge_class(value):
    """Retorna classes Tailwind para a sigla do código de ocorrência."""
    if not value:
        return 'bg-slate-100 text-slate-700'
    sigla = str(value).strip().upper()
    primeira = sigla[:1]
    mapa = {
        'A': 'bg-red-100 text-red-700',
        'B': 'bg-orange-100 text-orange-700',
        'C': 'bg-yellow-100 text-yellow-700',
        'D': 'bg-emerald-100 text-emerald-700',
        'E': 'bg-blue-100 text-blue-700',
        'F': 'bg-indigo-100 text-indigo-700',
        'G': 'bg-purple-100 text-purple-700',
    }
    return mapa.get(primeira, 'bg-slate-100 text-slate-700')

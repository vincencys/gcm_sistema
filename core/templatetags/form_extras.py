from django import template

register = template.Library()


@register.filter(name='add_class')
def add_class(field, css):
    """Adiciona classes CSS a um field renderizado.

    Uso: {{ form.campo|add_class:'w-full px-3 py-2' }}
    """
    try:
        existing = field.field.widget.attrs.get('class', '') if hasattr(field, 'field') else ''
        classes = (existing + ' ' + (css or '')).strip()
        return field.as_widget(attrs={'class': classes})
    except Exception:
        return field


@register.filter(name='format_cpf')
def format_cpf(value: str) -> str:
    """Formata CPF (somente dígitos) como 000.000.000-00."""
    try:
        digits = ''.join(c for c in (value or '') if c.isdigit())
        if len(digits) != 11:
            return value or ''
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    except Exception:
        return value or ''


@register.filter(name='format_cnpj')
def format_cnpj(value: str) -> str:
    """Formata CNPJ (somente dígitos) como 00.000.000/0000-00."""
    try:
        digits = ''.join(c for c in (value or '') if c.isdigit())
        if len(digits) != 14:
            return value or ''
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    except Exception:
        return value or ''


@register.filter(name='format_cpf_cnpj')
def format_cpf_cnpj(value: str) -> str:
    """Formata automaticamente CPF (11) ou CNPJ (14)."""
    try:
        digits = ''.join(c for c in (value or '') if c.isdigit())
        if len(digits) == 11:
            return format_cpf(digits)
        if len(digits) == 14:
            return format_cnpj(digits)
        return value or ''
    except Exception:
        return value or ''

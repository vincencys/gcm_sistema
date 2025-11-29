from django import template
import os

register = template.Library()

@register.filter
def is_image(path: str) -> bool:
    if not path:
        return False
    ext = os.path.splitext(str(path))[1].lower()
    return ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

@register.filter
def is_pdf(path: str) -> bool:
    if not path:
        return False
    ext = os.path.splitext(str(path))[1].lower()
    return ext == '.pdf'

@register.filter
def filename(path: str) -> str:
    return os.path.basename(str(path)) if path else ''

@register.filter
def mes_nome(mes_num):
    """Converte número do mês (1..12, str ou int) para nome PT-BR."""
    try:
        m = int(mes_num)
    except (TypeError, ValueError):
        return mes_num
    nomes = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
        7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    return nomes.get(m, str(mes_num))

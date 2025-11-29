
from django import template
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Q
from taloes.models import Talao

register = template.Library()

@register.filter
def subtract(value, arg):
    """Subtrai arg de value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return ''

@register.simple_tag(takes_context=True)
def taloes_ativas(context):
    """Renderiza bloco de viaturas ativas (para usar no CECOM)."""
    taloes = (Talao.objects.select_related("viatura","codigo_ocorrencia")
              .filter(status="ABERTO")
              .order_by("viatura__prefixo", "-iniciado_em"))
    html = render_to_string("taloes/_ativas.html", {"taloes": taloes})
    return html

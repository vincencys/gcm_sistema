from django import template

register = template.Library()

@register.filter(name='dict_get')
def dict_get(d, key):
    try:
        return d.get(key)
    except Exception:
        return None

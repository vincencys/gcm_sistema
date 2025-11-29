from django import template

register = template.Library()


@register.filter
def status_badge_class(status: str) -> str:
    s = (status or "").upper()
    base = "inline-flex items-center rounded px-2 py-0.5 text-xs border"
    mapping = {
        "PENDENTE": " text-amber-700 bg-amber-100 border-amber-300",
        "APROVADA": " text-blue-700 bg-blue-100 border-blue-300",
        "ABERTA": " text-emerald-700 bg-emerald-100 border-emerald-300",
        "ENCERRADA": " text-slate-700 bg-slate-100 border-slate-300",
        "ATRASADA": " text-red-700 bg-red-100 border-red-300",
        "CANCELADA": " text-slate-700 bg-slate-100 border-slate-300",
    }
    return base + mapping.get(s, " text-slate-700 bg-slate-100 border-slate-300")


@register.filter
def dict_get(d: dict, key):
    """Acessa d[key] com fallback para get; útil em templates.

    Ex.: {{ meu_dict|dict_get:obj.id }}
    """
    try:
        if d is None:
            return None
        return d.get(key)
    except Exception:
        return None

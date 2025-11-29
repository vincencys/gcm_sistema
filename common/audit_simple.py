from __future__ import annotations
from typing import Any, Optional
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from django.utils import timezone
from .models import SimpleLog


def record(
    request: Optional[HttpRequest],
    *,
    event: str,
    obj: Any | None = None,
    message: str = "",
    extra: dict | None = None,
    app: str | None = None,
) -> None:
    """Registra um evento no Log Simplificado.

    - request: opcional; se fornecida, captura user, ip, user-agent e path
    - event: nome curto do evento (ex.: "BO_CRIADO", "TALAO_ABERTO")
    - obj: alvo opcional; se informado, armazena content_type/object_id e um target_repr legível
    - message: breve descrição legível
    - extra: dicionário opcional serializado como texto (debug/inspeção)
    - app: rótulo do app (auto do obj._meta.app_label quando possível)
    """
    user = None
    ip = None
    ua = ""
    path = ""
    if request is not None:
        try:
            user = getattr(request, 'user', None)
        except Exception:
            user = None
        try:
            ip = request.META.get('HTTP_X_FORWARDED_FOR', '') or request.META.get('REMOTE_ADDR') or None
            if ip and ',' in ip:
                ip = ip.split(',')[0].strip()
        except Exception:
            ip = None
        try:
            ua = (request.META.get('HTTP_USER_AGENT', '') or '')[:512]
        except Exception:
            ua = ""
        try:
            path = getattr(request, 'path', '') or ''
        except Exception:
            path = ""

    content_type = None
    object_id = None
    target_repr = ""
    app_label = app or ""
    if obj is not None:
        try:
            ct = ContentType.objects.get_for_model(obj.__class__)
            content_type = ct
            object_id = getattr(obj, 'pk', None)
            app_label = app_label or obj._meta.app_label
            # Tenta montar uma representação curta e útil do alvo
            if hasattr(obj, '__str__'):
                target_repr = str(obj)[:255]
            else:
                target_repr = f"{obj.__class__.__name__}#{object_id}"[:255]
        except Exception:
            pass

    try:
        SimpleLog.objects.create(
            user=user,
            app_label=(app_label or "core")[:50],
            event=(event or "EVENTO")[:50],
            message=(message or "")[:255],
            content_type=content_type,
            object_id=object_id,
            target_repr=target_repr,
            path=path[:512],
            ip=ip,
            user_agent=ua,
            extra=SimpleLog.dumps(extra) if hasattr(SimpleLog, 'dumps') else (''),
            created_at=timezone.now(),
        )
    except Exception:
        # Não interromper o fluxo da aplicação por falha de logging simplificado
        pass

from __future__ import annotations
from typing import Any, Optional
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.http import HttpRequest
from .models import AuditTrail


def log_event(*, actor: Any | None, obj: Any, event: str, message: str = "",
              before: dict | None = None, after: dict | None = None,
              request: Optional[HttpRequest] = None) -> None:
    """Registra evento de auditoria forte com hash encadeado.

    - actor pode ser None (ex.: jobs), obj é uma instância de modelo
    - event: SOLICITAR/APROVAR/ENTREGAR/DEVOLVER/OUTRO
    - before/after são dicionários serializados como JSON textual
    - request opcional para capturar IP e user-agent
    """
    ct = ContentType.objects.get_for_model(obj.__class__)
    prev_hash = AuditTrail.latest_hash_for(obj)
    ip = None
    ua = ""
    if request is not None:
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '') or request.META.get('REMOTE_ADDR') or None
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
        ua = (request.META.get('HTTP_USER_AGENT', '') or '')[:512]
    AuditTrail.objects.create(
        actor=actor,
        content_type=ct,
        object_id=obj.pk,
        event=event,
        message=message[:255],
        before=AuditTrail.dumps(before or {}),
        after=AuditTrail.dumps(after or {}),
        hash_prev=prev_hash,
        ip=ip,
        user_agent=ua,
        created_at=timezone.now(),
    )

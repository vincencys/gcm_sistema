# taloes/tasks.py
from celery import shared_task
from django.utils import timezone

@shared_task
def ping_taloes():
    # apenas um exemplo simples
    return f"pong @ {timezone.now().isoformat()}"

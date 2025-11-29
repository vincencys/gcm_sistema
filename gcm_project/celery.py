import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gcm_project.settings")

app = Celery("gcm_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()  # procura tasks.py nos apps

# Exemplo de beat (agendador). Se usar, ative no celery beat.
# from celery.schedules import crontab
# app.conf.beat_schedule = {
#     "exemplo-diario": {
#         "task": "core.tasks.exemplo",
#         "schedule": crontab(minute=0, hour=3),  # 03:00 todos os dias
#     }
# }

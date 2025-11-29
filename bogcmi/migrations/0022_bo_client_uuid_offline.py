from django.db import migrations, models
import uuid
from django.utils import timezone

def gen_uuid(apps, schema_editor):
    BO = apps.get_model('bogcmi', 'BO')
    for bo in BO.objects.filter(client_uuid__isnull=True):
        bo.client_uuid = uuid.uuid4()
        bo.save(update_fields=['client_uuid'])

class Migration(migrations.Migration):
    dependencies = [
        ('bogcmi', '0021_bo_algemas_bo_autoridade_policial_bo_escrivao_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bo',
            name='client_uuid',
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='bo',
            name='offline',
            field=models.BooleanField(default=False, help_text='Marcado como True se criado offline e ainda não sincronizado plenamente.'),
        ),
        migrations.AddField(
            model_name='bo',
            name='synced_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(gen_uuid, migrations.RunPython.noop),
    ]

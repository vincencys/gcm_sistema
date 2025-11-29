from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0003_alter_documentoassinavel_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PushDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(db_index=True, max_length=255, unique=True)),
                ('platform', models.CharField(choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')], default='android', max_length=16)),
                ('app_version', models.CharField(blank=True, max_length=32)),
                ('device_info', models.CharField(blank=True, help_text='Modelo/OS/identificação livre', max_length=255)),
                ('enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='push_devices', to='auth.user')),
            ],
            options={'ordering': ('-last_seen',)},
        ),
        migrations.AddIndex(
            model_name='pushdevice',
            index=models.Index(fields=['user', 'platform'], name='common_push_user_plat_idx'),
        ),
    ]

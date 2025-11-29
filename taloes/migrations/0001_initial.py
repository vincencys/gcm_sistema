from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('viaturas', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='GrupoOcorrencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=20, unique=True)),
                ('titulo', models.CharField(max_length=120)),
            ],
            options={
                'verbose_name': 'Grupo de Ocorrência',
                'verbose_name_plural': 'Grupos de Ocorrência',
                'ordering': ('codigo',),
            },
        ),
        migrations.CreateModel(
            name='CodigoOcorrencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sigla', models.CharField(max_length=10, unique=True)),
                ('descricao', models.CharField(max_length=160)),
                ('grupo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='codigos', to='taloes.grupoocorrencia')),
            ],
            options={
                'verbose_name': 'Código de Ocorrência',
                'verbose_name_plural': 'Códigos de Ocorrência',
                'ordering': ('sigla',),
            },
        ),
        migrations.CreateModel(
            name='Talao',
            fields=[
                ('numero', models.AutoField(primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('ABERTO', 'Aberto'), ('FECHADO', 'Fechado')], db_index=True, default='ABERTO', max_length=10)),
                ('iniciado_em', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('encerrado_em', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('km_inicial', models.PositiveIntegerField(default=0)),
                ('km_final', models.PositiveIntegerField(blank=True, null=True)),
                ('relatorio', models.TextField(blank=True, default='')),
                ('equipe_texto', models.CharField(blank=True, default='', max_length=200)),
                ('local_bairro', models.CharField(blank=True, default='', max_length=120)),
                ('codigo_ocorrencia', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='taloes', to='taloes.codigoocorrencia')),
                ('criado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='taloes_criados', to=settings.AUTH_USER_MODEL)),
                ('viatura', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='taloes', to='viaturas.viatura')),
            ],
            options={
                'verbose_name': 'Talão',
                'verbose_name_plural': 'Talões',
                'ordering': ('-iniciado_em',),
            },
        ),
    ]

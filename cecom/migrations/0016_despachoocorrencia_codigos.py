from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('cecom', '0015_plantaocecom_verificacao_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='despachoocorrencia',
            name='cod_natureza',
            field=models.CharField(verbose_name='Código da Ocorrência', max_length=30, blank=True, default=''),
        ),
        migrations.AddField(
            model_name='despachoocorrencia',
            name='natureza',
            field=models.CharField(verbose_name='Descrição da Ocorrência', max_length=120, blank=True, default=''),
        ),
    ]

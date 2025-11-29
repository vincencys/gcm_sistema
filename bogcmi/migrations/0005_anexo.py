from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('bogcmi', '0004_alter_envolvido_cidade_and_more'),
    ]
    operations = [
        migrations.CreateModel(
            name='Anexo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descricao', models.CharField(max_length=120)),
                ('arquivo', models.FileField(upload_to='anexos/')),
                ('envolvido', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bogcmi.envolvido')),
            ],
        ),
    ]
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("taloes", "0001_initial"),
        ("bogcmi", "0023_bo_validacao_hash_bo_validacao_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="bo",
            name="talao",
            field=models.ForeignKey(
                to="taloes.talao",
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bos",
                null=True,
                blank=True,
                help_text="Talão de origem (se criado a partir de um talão).",
            ),
        ),
    ]

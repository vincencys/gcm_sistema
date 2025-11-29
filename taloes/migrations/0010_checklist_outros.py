from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("taloes", "0009_abastecimento"),
    ]

    operations = [
        migrations.AddField(
            model_name="checklistviatura",
            name="outros",
            field=models.TextField(verbose_name="Outros (descrever)", blank=True, default=""),
        ),
    ]

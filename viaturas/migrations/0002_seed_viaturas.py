from django.db import migrations

def seed_viaturas(apps, schema_editor):
    Viatura = apps.get_model("viaturas", "Viatura")

    registros = [
        ("25", "RANGER"),
        ("35", "ARGO"),
        ("36", "ARGO"),
        ("38", "TRAILBLAZER"),
        ("39", "L200"),
        ("40", "STRADA"),
        ("41", "PULSE"),
        ("MT11", "MOTOCICLETA"),
        ("MT12", "MOTOCICLETA"),
        ("MT13", "MOTOCICLETA"),
        ("MT14", "MOTOCICLETA"),
        ("MT15", "MOTOCICLETA"),
    ]

    # suporta 'ativo' OU 'ativa' (ou nenhum)
    field_names = {f.name for f in Viatura._meta.get_fields()}
    has_ativo = "ativo" in field_names
    has_ativa = "ativa" in field_names

    for prefixo, modelo in registros:
        defaults = {"modelo": modelo}
        if has_ativo:
            defaults["ativo"] = True
        if has_ativa:
            defaults["ativa"] = True
        Viatura.objects.update_or_create(prefixo=prefixo, defaults=defaults)

class Migration(migrations.Migration):

    dependencies = [
        ("viaturas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_viaturas, migrations.RunPython.noop),
    ]

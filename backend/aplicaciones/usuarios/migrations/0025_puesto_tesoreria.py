from django.db import migrations


def crear_puesto_tesoreria(apps, schema_editor):
    Puesto = apps.get_model('usuarios', 'Puesto')
    Puesto.objects.get_or_create(
        nombre='Tesorería',
        defaults={'descripcion': 'Responsable institucional de tesorería.'},
    )


def retirar_puesto_tesoreria(apps, schema_editor):
    Puesto = apps.get_model('usuarios', 'Puesto')
    Admin = apps.get_model('usuarios', 'Admin')
    Rol = apps.get_model('usuarios', 'Rol')
    puesto = Puesto.objects.filter(nombre='Tesorería').first()
    if puesto and not Admin.objects.filter(puesto_id=puesto.pk).exists() and not Rol.objects.filter(puesto_id=puesto.pk).exists():
        puesto.delete()


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0024_rol_puesto_institucional')]

    operations = [
        migrations.RunPython(crear_puesto_tesoreria, retirar_puesto_tesoreria),
    ]

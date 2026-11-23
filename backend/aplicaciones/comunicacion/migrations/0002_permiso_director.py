from django.db import migrations


def permisos(apps, schema_editor):
    model, _ = apps.get_model('usuarios', 'ModeloPermitido').objects.get_or_create(nombre='comunicacion')
    action, _ = apps.get_model('usuarios', 'Accion').objects.get_or_create(nombre='gestionar')
    for position in apps.get_model('usuarios', 'Puesto').objects.filter(nombre__iexact='Director'):
        apps.get_model('usuarios', 'PermisoPuesto').objects.get_or_create(puesto=position, modelo=model, accion=action)


class Migration(migrations.Migration):
    dependencies = [('comunicacion', '0001_initial'), ('usuarios', '0025_permiso_materia_director_secretaria')]
    operations = [migrations.RunPython(permisos, migrations.RunPython.noop)]

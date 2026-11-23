from django.db import migrations


def grant(apps, schema_editor):
    Puesto = apps.get_model('usuarios', 'Puesto')
    model, _ = apps.get_model('usuarios', 'ModeloPermitido').objects.get_or_create(nombre='portal-panel')
    action, _ = apps.get_model('usuarios', 'Accion').objects.get_or_create(nombre='listar')
    for puesto in Puesto.objects.all():
        if puesto.nombre.strip().lower() == 'director':
            apps.get_model('usuarios', 'PermisoPuesto').objects.get_or_create(puesto=puesto, modelo=model, accion=action)


def reverse(apps, schema_editor):
    apps.get_model('usuarios', 'PermisoPuesto').objects.filter(modelo__nombre='portal-panel', accion__nombre='listar').delete()


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0025_permiso_materia_director_secretaria')]
    operations = [migrations.RunPython(grant, reverse)]

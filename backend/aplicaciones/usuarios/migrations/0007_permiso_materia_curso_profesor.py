from django.db import migrations


def habilitar_materia_curso_profesor(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Accion = apps.get_model('usuarios', 'Accion')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')

    rol, _ = Rol.objects.get_or_create(
        nombre='Profesor',
        defaults={'descripcion': 'Personal docente'},
    )
    accion, _ = Accion.objects.get_or_create(nombre='listar')
    modelo, _ = Modelo.objects.get_or_create(nombre='materia-curso')
    PermisoRol.objects.get_or_create(rol=rol, modelo=modelo, accion=accion)


def revertir(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')
    PermisoRol.objects.filter(modelo__nombre='materia-curso').delete()
    Modelo.objects.filter(nombre='materia-curso').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0006_crud_tipo_feriado_director'),
    ]

    operations = [
        migrations.RunPython(habilitar_materia_curso_profesor, revertir),
    ]

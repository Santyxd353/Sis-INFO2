from django.db import migrations


def habilitar_perfil_estudiante(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Accion = apps.get_model('usuarios', 'Accion')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')

    rol, _ = Rol.objects.get_or_create(
        nombre='Estudiante',
        defaults={'descripcion': 'Estudiante de una unidad educativa'},
    )
    accion, _ = Accion.objects.get_or_create(nombre='listar')
    modelo, _ = Modelo.objects.get_or_create(nombre='estudiante')
    PermisoRol.objects.get_or_create(rol=rol, modelo=modelo, accion=accion)


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0003_roles_puestos_permisos_base'),
    ]

    operations = [
        migrations.RunPython(habilitar_perfil_estudiante, migrations.RunPython.noop),
    ]

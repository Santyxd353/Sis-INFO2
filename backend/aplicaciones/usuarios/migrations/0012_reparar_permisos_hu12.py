import unicodedata

from django.db import migrations


def normalizar_puesto(nombre):
    return ''.join(
        caracter
        for caracter in unicodedata.normalize('NFD', nombre.casefold())
        if unicodedata.category(caracter) != 'Mn'
    ).strip()


def seed_permisos_hu12(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Puesto = apps.get_model('usuarios', 'Puesto')
    Rol = apps.get_model('usuarios', 'Rol')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')

    modelo, _ = Modelo.objects.get_or_create(nombre='horario')
    puestos_autorizados = {'director', 'secretaria', 'administrador academico'}
    for nombre_accion in ('listar', 'crear', 'editar', 'eliminar'):
        accion, _ = Accion.objects.get_or_create(nombre=nombre_accion)
        for puesto in Puesto.objects.all():
            if normalizar_puesto(puesto.nombre) in puestos_autorizados:
                PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)
        if nombre_accion == 'listar':
            for rol in Rol.objects.filter(nombre__iexact='Profesor'):
                PermisoRol.objects.get_or_create(rol=rol, modelo=modelo, accion=accion)


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0011_permisos_hu12'),
    ]

    operations = [
        migrations.RunPython(seed_permisos_hu12, migrations.RunPython.noop),
    ]

import unicodedata

from django.db import migrations


def normalizar_puesto(nombre):
    return ''.join(
        caracter
        for caracter in unicodedata.normalize('NFD', nombre.casefold())
        if unicodedata.category(caracter) != 'Mn'
    ).strip()


def seed(apps, schema_editor):
    Model = apps.get_model('usuarios', 'ModeloPermitido')
    Action = apps.get_model('usuarios', 'Accion')
    Position = apps.get_model('usuarios', 'Puesto')
    Role = apps.get_model('usuarios', 'Rol')
    PositionPermission = apps.get_model('usuarios', 'PermisoPuesto')
    RolePermission = apps.get_model('usuarios', 'PermisoRol')
    model, _ = Model.objects.get_or_create(nombre='horario')
    for name in ('listar', 'crear', 'editar', 'eliminar'):
        action, _ = Action.objects.get_or_create(nombre=name)
        for position in Position.objects.all():
            if normalizar_puesto(position.nombre) in {'director', 'secretaria', 'administrador academico'}:
                PositionPermission.objects.get_or_create(puesto=position, modelo=model, accion=action)
        if name == 'listar':
            for role in Role.objects.filter(nombre__iexact='Profesor'):
                RolePermission.objects.get_or_create(rol=role, modelo=model, accion=action)


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0011_merge_20261016_1531')]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]

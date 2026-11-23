from django.db import migrations


def seed(apps, schema_editor):
    Model = apps.get_model('usuarios', 'ModeloPermitido')
    Action = apps.get_model('usuarios', 'Accion')
    Position = apps.get_model('usuarios', 'Puesto')
    Role = apps.get_model('usuarios', 'Rol')
    PositionPermission = apps.get_model('usuarios', 'PermisoPuesto')
    RolePermission = apps.get_model('usuarios', 'PermisoRol')
    for model_name, positions in (
        ('disciplina', ('Director', 'Regente', 'Administrador académico')),
        ('correccion-nota', ('Director', 'Administrador académico')),
    ):
        model, _ = Model.objects.get_or_create(nombre=model_name)
        for name in ('listar', 'crear', 'editar'):
            action, _ = Action.objects.get_or_create(nombre=name)
            for title in positions:
                for position in Position.objects.filter(nombre__iexact=title):
                    PositionPermission.objects.get_or_create(puesto=position, modelo=model, accion=action)
            role_name = 'Regente' if model_name == 'disciplina' else 'Profesor'
            if model_name == 'disciplina' or name != 'editar':
                for role in Role.objects.filter(nombre__iexact=role_name):
                    RolePermission.objects.get_or_create(rol=role, modelo=model, accion=action)


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0009_admin_colegio_expand_contract')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

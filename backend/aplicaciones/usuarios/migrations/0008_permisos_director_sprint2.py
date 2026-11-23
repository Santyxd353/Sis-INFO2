from django.db import migrations


def completar_permisos_director(apps, schema_editor):
    Puesto = apps.get_model('usuarios', 'Puesto')
    Accion = apps.get_model('usuarios', 'Accion')
    ModeloPermitido = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')

    director = Puesto.objects.filter(nombre__iexact='Director').first()
    if director is None:
        return

    for modelo_nombre, acciones in {
        'asignacion-docente': ('listar', 'crear', 'editar'),
        'auditoria': ('listar',),
    }.items():
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre=modelo_nombre)
        for accion_nombre in acciones:
            accion, _ = Accion.objects.get_or_create(nombre=accion_nombre)
            PermisoPuesto.objects.get_or_create(
                puesto=director, modelo=modelo, accion=accion,
            )


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0007_sprint2_bloque1')]

    operations = [
        migrations.RunPython(completar_permisos_director, migrations.RunPython.noop),
    ]

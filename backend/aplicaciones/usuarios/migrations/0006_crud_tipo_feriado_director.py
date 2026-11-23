from django.db import migrations


def habilitar_crud_tipo_feriado(apps, schema_editor):
    Puesto = apps.get_model('usuarios', 'Puesto')
    Accion = apps.get_model('usuarios', 'Accion')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')

    director, _ = Puesto.objects.get_or_create(nombre='Director')
    modelo, _ = Modelo.objects.get_or_create(nombre='tipo-feriado')
    for nombre in ('listar', 'crear', 'editar', 'eliminar'):
        accion, _ = Accion.objects.get_or_create(nombre=nombre)
        PermisoPuesto.objects.get_or_create(
            puesto=director, modelo=modelo, accion=accion
        )


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0005_convertir_roles_administrativos_heredados'),
    ]

    operations = [
        migrations.RunPython(habilitar_crud_tipo_feriado, migrations.RunPython.noop),
    ]

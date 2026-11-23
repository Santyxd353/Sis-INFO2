from django.db import migrations


# HU-SE02: acciones funcionales adicionales del catálogo.
ACCIONES_HU_SE02 = ('desactivar', 'aprobar', 'exportar', 'administrar')

# Permisos funcionales por puesto sobre el modelo 'rol' (gestión de roles).
PERMISOS_PUESTO_ROL = {
    'Director': ('listar', 'crear', 'editar', 'eliminar'),
    'Secretaria': ('listar',),
}


def seed_hu_se02(apps, schema_editor):
    Accion = apps.get_model('usuarios', 'Accion')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Puesto = apps.get_model('usuarios', 'Puesto')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')

    modelo_rol, _ = Modelo.objects.get_or_create(nombre='rol')
    nombres_accion = (
        'listar', 'crear', 'editar', 'eliminar', *ACCIONES_HU_SE02,
    )
    acciones = {
        nombre: Accion.objects.get_or_create(nombre=nombre)[0]
        for nombre in nombres_accion
    }

    for puesto_nombre, nombres_accion in PERMISOS_PUESTO_ROL.items():
        puesto, _ = Puesto.objects.get_or_create(
            nombre=puesto_nombre,
            defaults={'descripcion': f'{puesto_nombre} (HU-SE02)'},
        )
        for accion_nombre in nombres_accion:
            PermisoPuesto.objects.get_or_create(
                puesto=puesto, modelo=modelo_rol, accion=acciones[accion_nombre],
            )


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0013_hu_se02_roles_granulares'),
    ]

    operations = [
        migrations.RunPython(seed_hu_se02, migrations.RunPython.noop),
    ]

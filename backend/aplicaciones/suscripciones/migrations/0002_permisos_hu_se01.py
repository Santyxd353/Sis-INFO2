from django.db import migrations


MODELOS_HU_SE01 = ('plan', 'suscripcion', 'pago')

# Permisos de plataforma (gestión de suscripciones del colegio).
PERMISOS_PUESTO = {
    'Director': {
        'suscripcion': ('listar', 'crear'),
        'pago': ('listar',),
    },
    'Secretaria': {
        'suscripcion': ('listar',),
        'pago': ('listar',),
    },
    'Administrador Institucional': {
        'suscripcion': ('listar', 'crear'),
        'pago': ('listar',),
    },
}


def crear_permisos_suscripciones(apps, schema_editor):
    Accion = apps.get_model('usuarios', 'Accion')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Puesto = apps.get_model('usuarios', 'Puesto')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')

    modelos = {
        nombre: Modelo.objects.get_or_create(nombre=nombre)[0]
        for nombre in MODELOS_HU_SE01
    }
    acciones = {
        nombre: Accion.objects.get_or_create(nombre=nombre)[0]
        for nombre in ('listar', 'crear', 'editar', 'eliminar')
    }

    for puesto_nombre, permisos in PERMISOS_PUESTO.items():
        puesto, _ = Puesto.objects.get_or_create(
            nombre=puesto_nombre,
            defaults={'descripcion': f'{puesto_nombre} (HU-SE01)'},
        )
        for modelo_nombre, nombres_accion in permisos.items():
            for accion_nombre in nombres_accion:
                PermisoPuesto.objects.get_or_create(
                    puesto=puesto,
                    modelo=modelos[modelo_nombre],
                    accion=acciones[accion_nombre],
                )


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0010_merge_20261016_1159'),
        ('institucion', '0005_sprint2_bloque2'),
        ('suscripciones', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_permisos_suscripciones, migrations.RunPython.noop),
    ]

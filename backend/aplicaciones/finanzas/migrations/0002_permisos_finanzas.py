from django.db import migrations

RECURSOS = {
    'plan-pago': ('listar', 'crear', 'editar', 'desactivar', 'asignar'),
    'beca': ('listar', 'crear', 'editar', 'desactivar', 'asignar'),
    'obligacion-pago': ('listar', 'editar'),
}
PUESTOS = ('Director', 'Secretaria')


def sembrar(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Puesto = apps.get_model('usuarios', 'Puesto')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    puestos = [Puesto.objects.get_or_create(nombre=nombre)[0] for nombre in PUESTOS]
    for recurso, acciones in RECURSOS.items():
        modelo, _ = Modelo.objects.get_or_create(nombre=recurso)
        for nombre in acciones:
            accion, _ = Accion.objects.get_or_create(nombre=nombre)
            for puesto in puestos:
                PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)


def revertir(apps, schema_editor):
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    PermisoPuesto.objects.filter(modelo__nombre__in=RECURSOS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('finanzas', '0001_initial'),
        ('usuarios', '0025_permiso_materia_director_secretaria'),
    ]

    operations = [migrations.RunPython(sembrar, revertir)]

from django.db import migrations

ACCIONES = ('listar', 'crear', 'conciliar')
PUESTOS = ('Director', 'Secretaria')


def sembrar(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Puesto = apps.get_model('usuarios', 'Puesto')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    modelo, _ = Modelo.objects.get_or_create(nombre='pago-qr')
    for nombre_puesto in PUESTOS:
        puesto, _ = Puesto.objects.get_or_create(nombre=nombre_puesto)
        for nombre in ACCIONES:
            accion, _ = Accion.objects.get_or_create(nombre=nombre)
            PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)


def revertir(apps, schema_editor):
    apps.get_model('usuarios', 'PermisoPuesto').objects.filter(modelo__nombre='pago-qr').delete()


class Migration(migrations.Migration):
    dependencies = [('finanzas', '0005_solicitud_qr')]

    operations = [migrations.RunPython(sembrar, revertir)]

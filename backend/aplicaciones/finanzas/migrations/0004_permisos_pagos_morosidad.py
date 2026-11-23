from django.db import migrations

RECURSOS = {
    'pago': ('listar', 'crear', 'anular'),
    'estado-cuenta': ('listar',),
    'morosidad': ('listar',),
    'simulacion-tributaria': ('listar',),
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
    dependencies = [('finanzas', '0003_pagos')]

    operations = [migrations.RunPython(sembrar, revertir)]

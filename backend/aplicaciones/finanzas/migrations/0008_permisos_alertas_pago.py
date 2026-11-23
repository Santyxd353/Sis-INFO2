"""HU-28: permisos de alertas de pago para Director y Secretaria.

Tesorería no recibe permisos implícitos por puesto: se le otorgan con un rol
funcional (PermisoRol), como define el módulo de usuarios.
"""
from django.db import migrations

ALERTAS = {'alerta-pago': ('listar', 'crear')}
PUESTOS = ('Director', 'Secretaria')


def sembrar(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Puesto = apps.get_model('usuarios', 'Puesto')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    for nombre_puesto in PUESTOS:
        puesto, _ = Puesto.objects.get_or_create(nombre=nombre_puesto)
        for recurso, acciones in ALERTAS.items():
            modelo, _ = Modelo.objects.get_or_create(nombre=recurso)
            for nombre in acciones:
                accion, _ = Accion.objects.get_or_create(nombre=nombre)
                PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)


def revertir(apps, schema_editor):
    apps.get_model('usuarios', 'PermisoPuesto').objects.filter(modelo__nombre__in=ALERTAS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('finanzas', '0007_recordatorio_pago'),
        ('usuarios', '0026_merge_tesoreria_materia'),
    ]

    operations = [migrations.RunPython(sembrar, revertir)]

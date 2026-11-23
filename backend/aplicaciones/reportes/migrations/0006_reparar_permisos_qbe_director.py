from django.db import migrations


def sembrar(apps, schema_editor):
    Puesto = apps.get_model('usuarios', 'Puesto')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Permiso = apps.get_model('usuarios', 'PermisoPuesto')
    modelo, _ = Modelo.objects.get_or_create(nombre='reporte-qbe')
    for puesto in Puesto.objects.filter(nombre__iexact='Director'):
        for nombre in ('validar', 'ejecutar'):
            accion, _ = Accion.objects.get_or_create(nombre=nombre)
            Permiso.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)


class Migration(migrations.Migration):
    dependencies = [('reportes', '0005_reportedefinicion_descripcion')]
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]

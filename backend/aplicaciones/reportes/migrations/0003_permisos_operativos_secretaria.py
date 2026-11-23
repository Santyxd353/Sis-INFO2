from django.db import migrations


def sembrar(apps, schema_editor):
    Puesto = apps.get_model('usuarios', 'Puesto')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Permiso = apps.get_model('usuarios', 'PermisoPuesto')
    recursos = {'reporte-definicion': ('listar', 'crear', 'editar', 'archivar'),
                'reporte-ejecucion': ('listar', 'ejecutar', 'descargar')}
    for puesto in Puesto.objects.filter(nombre__iexact='Secretaria'):
        for nombre, acciones in recursos.items():
            modelo = Modelo.objects.get(nombre=nombre)
            for nombre_accion in acciones:
                accion = Accion.objects.get(nombre=nombre_accion)
                Permiso.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)


class Migration(migrations.Migration):
    dependencies = [('reportes', '0002_permisos')]
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]

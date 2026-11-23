from django.db import migrations


RECURSOS = {
    'reporte-definicion': ('listar', 'crear', 'editar', 'archivar'),
    'reporte-ejecucion': ('listar', 'ejecutar', 'descargar'),
    'reporte-qbe': ('validar', 'ejecutar'),
    'reporte-analitico': ('listar',),
    'reporte-voz': ('interpretar',),
}


def sembrar(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Puesto = apps.get_model('usuarios', 'Puesto')
    Permiso = apps.get_model('usuarios', 'PermisoPuesto')
    directores = Puesto.objects.filter(nombre__iexact='Director')
    for recurso, acciones in RECURSOS.items():
        modelo, _ = Modelo.objects.get_or_create(nombre=recurso)
        for nombre in acciones:
            accion, _ = Accion.objects.get_or_create(nombre=nombre)
            for puesto in directores:
                Permiso.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)


class Migration(migrations.Migration):
    dependencies = [('reportes', '0001_initial'), ('usuarios', '0012_reparar_permisos_hu12')]
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]

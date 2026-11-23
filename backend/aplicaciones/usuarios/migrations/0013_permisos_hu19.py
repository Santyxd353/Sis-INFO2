import unicodedata
from django.db import migrations


def sembrar(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Puesto = apps.get_model('usuarios', 'Puesto')
    Permiso = apps.get_model('usuarios', 'PermisoPuesto')
    modelo, _ = Modelo.objects.get_or_create(nombre='documento-academico')
    for nombre in ('listar', 'generar', 'descargar'):
        accion, _ = Accion.objects.get_or_create(nombre=nombre)
        for puesto in Puesto.objects.all():
            normal = ''.join(c for c in unicodedata.normalize('NFD', puesto.nombre.casefold()) if unicodedata.category(c) != 'Mn').strip()
            if normal in ('director', 'secretaria'):
                Permiso.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0012_reparar_permisos_hu12'), ('usuarios', '0011_merge_20261016_1531')]
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]

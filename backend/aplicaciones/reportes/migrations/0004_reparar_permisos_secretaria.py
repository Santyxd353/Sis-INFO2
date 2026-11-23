from django.db import migrations
import unicodedata


PERMISOS = {
    'reporte-definicion': ('listar', 'crear', 'editar', 'archivar'),
    'reporte-ejecucion': ('listar', 'ejecutar', 'descargar'),
}


def normalizar(valor):
    texto = unicodedata.normalize('NFD', str(valor or '').strip().lower())
    return ''.join(c for c in texto if unicodedata.category(c) != 'Mn')


def reparar(apps, schema_editor):
    Puesto = apps.get_model('usuarios', 'Puesto')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Permiso = apps.get_model('usuarios', 'PermisoPuesto')
    for puesto in Puesto.objects.all():
        if normalizar(puesto.nombre) != 'secretaria':
            continue
        for recurso, acciones in PERMISOS.items():
            modelo = Modelo.objects.get(nombre=recurso)
            for nombre_accion in acciones:
                accion = Accion.objects.get(nombre=nombre_accion)
                Permiso.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)


class Migration(migrations.Migration):
    dependencies = [('reportes', '0003_permisos_operativos_secretaria')]
    operations = [migrations.RunPython(reparar, migrations.RunPython.noop)]

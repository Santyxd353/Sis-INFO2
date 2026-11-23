from django.db import migrations


MODELO = 'comunicado'
ACCIONES = ('listar', 'crear', 'editar', 'publicar', 'archivar', 'descargar')


def crear_catalogo(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Puesto = apps.get_model('usuarios', 'Puesto')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    PermisoComponente = apps.get_model('usuarios', 'PermisoComponente')
    Rol = apps.get_model('usuarios', 'Rol')
    Modelo.objects.get_or_create(nombre=MODELO)
    modelo = Modelo.objects.get(nombre=MODELO)
    puesto, _ = Puesto.objects.get_or_create(nombre='Director')
    for nombre in ACCIONES:
        accion, _ = Accion.objects.get_or_create(nombre=nombre)
        PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)
    # El rol base no se crea ni se cambia. Este componente solo muestra la UI;
    # los permisos efectivos del puesto siguen siendo obligatorios para operar.
    rol_admin = Rol.objects.filter(nombre='Admin').first()
    if rol_admin:
        PermisoComponente.objects.get_or_create(
            rol=rol_admin, componente='modulo:comunicaciones',
            defaults={'visible': True, 'editable': True},
        )


def quitar_catalogo(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    modelo = Modelo.objects.filter(nombre=MODELO).first()
    Puesto = apps.get_model('usuarios', 'Puesto')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    if modelo:
        PermisoPuesto.objects.filter(puesto__nombre='Director', modelo=modelo).delete()
    PermisoComponente = apps.get_model('usuarios', 'PermisoComponente')
    Rol = apps.get_model('usuarios', 'Rol')
    rol_admin = Rol.objects.filter(nombre='Admin').first()
    if rol_admin:
        PermisoComponente.objects.filter(rol=rol_admin, componente='modulo:comunicaciones').delete()
    if modelo and not modelo.permisorol_set.exists() and not modelo.permisopuesto_set.exists():
        modelo.delete()
    for nombre in ACCIONES:
        accion = Accion.objects.filter(nombre=nombre).first()
        if accion and not accion.permisorol_set.exists() and not accion.permisopuesto_set.exists():
            accion.delete()


class Migration(migrations.Migration):
    dependencies = [('comunicaciones', '0001_initial'), ('usuarios', '0014_hu_se02_datos')]
    operations = [migrations.RunPython(crear_catalogo, quitar_catalogo)]

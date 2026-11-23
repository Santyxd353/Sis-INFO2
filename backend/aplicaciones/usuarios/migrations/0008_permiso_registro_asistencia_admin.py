from django.db import migrations


def habilitar_registro_asistencia_admin(apps, schema_editor):
    """Permite al regente/direccion y secretaria tomar asistencia.

    El rol Admin (sin perfil de puesto) y los puestos Director/Secretaria
    necesitan listar cursos y asignaciones para poder usar el formulario
    de registro de asistencia.
    """
    Rol = apps.get_model('usuarios', 'Rol')
    Puesto = apps.get_model('usuarios', 'Puesto')
    Accion = apps.get_model('usuarios', 'Accion')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')

    listar, _ = Accion.objects.get_or_create(nombre='listar')

    rol_admin, _ = Rol.objects.get_or_create(
        nombre='Admin',
        defaults={'descripcion': 'Personal administrativo'},
    )
    for nombre_modelo in ('curso', 'materia-curso'):
        modelo, _ = Modelo.objects.get_or_create(nombre=nombre_modelo)
        PermisoRol.objects.get_or_create(rol=rol_admin, modelo=modelo, accion=listar)

    modelo_asignacion, _ = Modelo.objects.get_or_create(nombre='materia-curso')
    for nombre_puesto in ('Director', 'Secretaria'):
        puesto, _ = Puesto.objects.get_or_create(nombre=nombre_puesto)
        PermisoPuesto.objects.get_or_create(
            puesto=puesto, modelo=modelo_asignacion, accion=listar,
        )


def revertir(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Puesto = apps.get_model('usuarios', 'Puesto')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')

    rol_admin = Rol.objects.filter(nombre='Admin').first()
    if rol_admin:
        PermisoRol.objects.filter(
            rol=rol_admin, modelo__nombre__in=('curso', 'materia-curso'),
        ).delete()

    PermisoPuesto.objects.filter(modelo__nombre='materia-curso').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0007_permiso_materia_curso_profesor'),
    ]

    operations = [
        migrations.RunPython(habilitar_registro_asistencia_admin, revertir),
    ]

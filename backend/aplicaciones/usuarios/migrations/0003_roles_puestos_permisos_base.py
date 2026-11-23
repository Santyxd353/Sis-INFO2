from django.db import migrations


ROLES = {
    'SuperAdmin': 'Administración global de la plataforma',
    'Admin': 'Personal administrativo de una unidad educativa',
    'Profesor': 'Personal docente',
    'Tutor': 'Tutor o responsable de estudiantes',
    'Estudiante': 'Estudiante de una unidad educativa',
}

MODELOS = [
    'colegio', 'unidad-educativa', 'usuario', 'calendario', 'periodo',
    'tipo-feriado', 'feriado', 'grado', 'paralelo', 'curso', 'profesor',
    'estudiante', 'tutor', 'tutor-estudiante',
]

PERMISOS_SECRETARIA = {
    'unidad-educativa': ['listar'],
    'usuario': ['listar', 'crear', 'editar'],
    'calendario': ['listar'],
    'periodo': ['listar'],
    'grado': ['listar'],
    'paralelo': ['listar'],
    'curso': ['listar'],
    'profesor': ['listar'],
    'estudiante': ['listar', 'crear', 'editar'],
    'tutor': ['listar', 'crear', 'editar'],
    'tutor-estudiante': ['listar', 'crear', 'editar', 'eliminar'],
}


def crear_catalogo(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Puesto = apps.get_model('usuarios', 'Puesto')
    Accion = apps.get_model('usuarios', 'Accion')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')

    roles = {}
    for nombre, descripcion in ROLES.items():
        roles[nombre], _ = Rol.objects.get_or_create(
            nombre=nombre, defaults={'descripcion': descripcion}
        )

    acciones = {
        nombre: Accion.objects.get_or_create(nombre=nombre)[0]
        for nombre in ('listar', 'crear', 'editar', 'eliminar')
    }
    modelos = {
        nombre: Modelo.objects.get_or_create(nombre=nombre)[0]
        for nombre in MODELOS
    }
    director, _ = Puesto.objects.get_or_create(
        nombre='Director', defaults={'descripcion': 'Dirección de unidad educativa'}
    )
    secretaria, _ = Puesto.objects.get_or_create(
        nombre='Secretaria', defaults={'descripcion': 'Gestión administrativa y estudiantil'}
    )

    for modelo_nombre, modelo in modelos.items():
        if modelo_nombre in {'colegio', 'unidad-educativa'}:
            acciones_director = ('listar', 'editar')
        elif modelo_nombre == 'tipo-feriado':
            acciones_director = ('listar',)
        else:
            acciones_director = acciones.keys()
        for accion_nombre in acciones_director:
            PermisoPuesto.objects.get_or_create(
                puesto=director, modelo=modelo, accion=acciones[accion_nombre]
            )

    for modelo_nombre, nombres_accion in PERMISOS_SECRETARIA.items():
        for accion_nombre in nombres_accion:
            PermisoPuesto.objects.get_or_create(
                puesto=secretaria,
                modelo=modelos[modelo_nombre],
                accion=acciones[accion_nombre],
            )

    for rol_nombre, modelos_rol in {
        'Profesor': ('curso', 'estudiante'),
        'Tutor': ('estudiante',),
        'Estudiante': ('curso',),
    }.items():
        for modelo_nombre in modelos_rol:
            PermisoRol.objects.get_or_create(
                rol=roles[rol_nombre],
                modelo=modelos[modelo_nombre],
                accion=acciones['listar'],
            )


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0002_usuario_unidad_y_cambio_password'),
    ]

    operations = [migrations.RunPython(crear_catalogo, migrations.RunPython.noop)]

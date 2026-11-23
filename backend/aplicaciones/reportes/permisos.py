"""Permisos predeterminados para perfiles operativos de reportes."""
from aplicaciones.usuarios.tenancy import normalizar_nombre


PERMISOS_SECRETARIA_OPERATIVOS = {
    'reporte-definicion': ('listar', 'crear', 'editar', 'archivar'),
    'reporte-ejecucion': ('listar', 'ejecutar', 'descargar'),
}

PERMISOS_DIRECTOR_REPORTES = {
    **PERMISOS_SECRETARIA_OPERATIVOS,
    'reporte-qbe': ('validar', 'ejecutar'),
}


def es_secretaria(puesto):
    return normalizar_nombre(getattr(puesto, 'nombre', '')) == 'secretaria'


def otorgar_permisos_secretaria(puesto):
    """Otorga únicamente los permisos operativos definidos para Secretaría."""
    if not es_secretaria(puesto):
        return
    from aplicaciones.usuarios.models import Accion, ModeloPermitido, PermisoPuesto

    for recurso, acciones in PERMISOS_SECRETARIA_OPERATIVOS.items():
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre=recurso)
        for nombre_accion in acciones:
            accion, _ = Accion.objects.get_or_create(nombre=nombre_accion)
            PermisoPuesto.objects.get_or_create(
                puesto=puesto, modelo=modelo, accion=accion,
            )


def otorgar_permisos_director(puesto):
    if normalizar_nombre(getattr(puesto, 'nombre', '')) != 'director':
        return
    from aplicaciones.usuarios.models import Accion, ModeloPermitido, PermisoPuesto
    for recurso, acciones in PERMISOS_DIRECTOR_REPORTES.items():
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre=recurso)
        for nombre in acciones:
            accion, _ = Accion.objects.get_or_create(nombre=nombre)
            PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)

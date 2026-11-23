"""Validaciones cerradas; no se ejecutan consultas configuradas por clientes."""
import re
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied
from aplicaciones.usuarios.models import PermisoPuesto, PermisoRol
from aplicaciones.usuarios.tenancy import resolver_alcance

_PROHIBIDAS = ('sql', 'table', 'model_path', 'orm_path', 'password', 'token',
               'authorization', 'secret', 'audio', 'transcripcion', 'resultados', 'results')
_SQL = re.compile(r'\b(select|insert|update|delete|drop|alter|create|truncate|union|bearer|password|token|secret)\b', re.I)


def validar_json(valor):
    if isinstance(valor, dict):
        for clave, item in valor.items():
            if any(p in str(clave).lower() for p in _PROHIBIDAS):
                raise ValidationError('La estructura contiene una clave prohibida.')
            validar_json(item)
    elif isinstance(valor, list):
        for item in valor:
            validar_json(item)
    elif isinstance(valor, str) and (_SQL.search(valor) or len(valor) > 500):
        raise ValidationError('La estructura contiene texto no permitido.')


def tiene_permiso(usuario, recurso, accion):
    if not usuario or not usuario.is_authenticated or not usuario.is_active:
        return False
    if hasattr(usuario, 'admin'):
        return PermisoPuesto.objects.filter(puesto_id=usuario.admin.puesto_id, modelo__nombre=recurso, accion__nombre=accion).exists()
    return PermisoRol.objects.filter(rol_id=usuario.rol_id, modelo__nombre=recurso, accion__nombre=accion).exists()


def validar_contexto(usuario, colegio_id, unidad_id=None):
    if not colegio_id:
        raise PermissionDenied('Se requiere un colegio explícito.')
    alcance = resolver_alcance(usuario)
    if alcance['tipo'] != 'GLOBAL' and alcance['colegio_id'] != colegio_id:
        raise PermissionDenied('Colegio fuera del alcance.')
    if alcance['tipo'] in ('UNIDAD', 'PERSONAL') and alcance['unidad_id'] != unidad_id:
        raise PermissionDenied('Unidad fuera del alcance.')
    return alcance

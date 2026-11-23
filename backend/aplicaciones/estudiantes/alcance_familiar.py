"""Shared family scope for portal projections and private academic documents."""
from django.db.models import F, Q
from rest_framework.exceptions import PermissionDenied
from aplicaciones.comunicacion.seguridad import usuarios_unidad
from aplicaciones.usuarios.tenancy import es_superadmin, normalizar_nombre
from .models import Estudiante


def coherent_students(qs):
    return qs.filter(estado=True, usuario__estado=True, usuario__is_active=True, usuario__rol__activo=True,
        unidad__isnull=False, unidad__colegio__isnull=False, usuario__unidad_id=F('unidad_id')).filter(
        Q(curso__isnull=True) | Q(curso__paralelo__grado__unidad_educativa_id=F('unidad_id')))


def family_students(user):
    role = normalizar_nombre(getattr(user.rol, 'nombre', ''))
    if (not user.estado or not user.is_active or not user.rol_id or not user.rol.activo or es_superadmin(user)
            or role not in ('tutor', 'estudiante') or not user.unidad_id
            or not usuarios_unidad(user.unidad_id).filter(pk=user.pk).exists()
            or (role == 'tutor' and not hasattr(user, 'tutor'))
            or (role == 'estudiante' and not hasattr(user, 'estudiante'))
            or hasattr(user, 'admin') or hasattr(user, 'profesor')):
        raise PermissionDenied('Se requiere un perfil familiar institucional coherente.')
    students = coherent_students(Estudiante.objects.all())
    return students.filter(pk=user.pk, unidad_id=user.unidad_id) if role == 'estudiante' else students.filter(
        tutores__tutor__usuario=user, unidad__colegio_id=user.unidad.colegio_id)

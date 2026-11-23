from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from aplicaciones.usuarios.feature_access import granted
from aplicaciones.usuarios.models import Usuario
from aplicaciones.usuarios.tenancy import es_superadmin, normalizar_nombre, unidades_permitidas, validar_unidad


def puede_gestionar(usuario):
    admin = getattr(usuario, 'admin', None)
    # Plataforma global no implica ser director de una institución.
    if (es_superadmin(usuario) or not admin or not admin.estado or not usuario.rol.activo
            or not usuario.estado or not usuario.is_active):
        return False
    if normalizar_nombre(usuario.rol.nombre) != 'admin' or normalizar_nombre(getattr(admin.puesto, 'nombre', '')) != 'director':
        return False
    # Resuelve y valida colegio/unidad incluso para listados vacíos.
    unidades_permitidas(usuario)
    return granted(usuario, 'comunicacion', 'gestionar')


def exigir_gestor(usuario, unidad):
    if not puede_gestionar(usuario):
        raise PermissionDenied('Se requiere un director con permiso de comunicación institucional.')
    validar_unidad(usuario, unidad)


def usuarios_unidad(unidad_id):
    """Exige afiliación actual coherente; un vínculo tutor no cruza tenants."""
    return Usuario.objects.filter(
        unidad_id=unidad_id, is_active=True, estado=True, rol__activo=True,
    ).filter(
        Q(estudiante__isnull=True) | Q(estudiante__unidad_id=unidad_id, estudiante__estado=True),
    ).filter(
        Q(profesor__isnull=True) | Q(profesor__unidad_id=unidad_id),
    ).filter(
        Q(admin__isnull=True) | Q(admin__unidad_id=unidad_id, admin__estado=True,
                                  admin__colegio_id=models_colegio(unidad_id))
        | Q(admin__unidad__isnull=True, admin__estado=True, admin__colegio_id=models_colegio(unidad_id)),
    )


def models_colegio(unidad_id):
    from aplicaciones.institucion.models import UnidadEducativa
    return UnidadEducativa.objects.filter(pk=unidad_id).values('colegio_id')[:1]


def audiencia_curso(unidad_id, curso_id):
    from aplicaciones.estudiantes.models import Estudiante, TutorEstudiante
    estudiantes = Estudiante.objects.filter(unidad_id=unidad_id, curso_id=curso_id, estado=True,
                                            usuario__unidad_id=unidad_id, usuario__is_active=True, usuario__estado=True)
    ids = set(estudiantes.values_list('usuario_id', flat=True))
    ids.update(TutorEstudiante.objects.filter(estudiante__in=estudiantes).values_list('tutor_id', flat=True))
    return usuarios_unidad(unidad_id).filter(pk__in=ids)

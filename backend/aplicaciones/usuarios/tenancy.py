import unicodedata

from rest_framework.exceptions import PermissionDenied


class ErrorAlcanceInstitucional(PermissionDenied):
    default_detail = 'El usuario no tiene un contexto institucional válido.'


def normalizar_nombre(valor):
    texto = unicodedata.normalize('NFD', str(valor or '').strip().lower())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return ' '.join(texto.replace('_', ' ').replace('-', ' ').split())


def es_superadmin(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    if hasattr(user, 'superadmin'):
        return True
    rol = getattr(user, 'rol', None)
    return rol is not None and rol.colegio_id is None and rol.activo and normalizar_nombre(rol.nombre) in {
        'superadmin', 'super admin',
    }


def resolver_alcance(user):
    """Resuelve el tenant desde la asignación institucional validada del perfil."""
    if es_superadmin(user):
        return {'tipo': 'GLOBAL', 'colegio_id': None, 'unidad_id': None}
    if not getattr(user, 'is_authenticated', False):
        raise ErrorAlcanceInstitucional('El usuario no está autenticado.')

    unidad = getattr(user, 'unidad', None)
    if hasattr(user, 'admin'):
        admin = user.admin
        unidad_admin = admin.unidad
        if unidad is not None and unidad_admin is not None and unidad.pk != unidad_admin.pk:
            raise ErrorAlcanceInstitucional(
                'La unidad del usuario no coincide con la unidad de su perfil administrativo.'
            )
        unidad = unidad or unidad_admin
        rol = normalizar_nombre(getattr(getattr(user, 'rol', None), 'nombre', ''))
        puesto = normalizar_nombre(getattr(admin.puesto, 'nombre', ''))
        if rol == 'admin' and puesto == 'tesoreria':
            colegio_id = admin.colegio_id
            if colegio_id is None:
                raise ErrorAlcanceInstitucional('Tesorería no tiene un colegio asignado.')
            if unidad is not None and unidad.colegio_id != colegio_id:
                raise ErrorAlcanceInstitucional(
                    'La unidad asignada a Tesorería no pertenece a su colegio.'
                )
            if unidad is not None and unidad_admin is None:
                raise ErrorAlcanceInstitucional(
                    'La unidad del usuario no coincide con su perfil administrativo.'
                )
            return {
                'tipo': 'UNIDAD' if unidad is not None else 'COLEGIO',
                'colegio_id': colegio_id,
                'unidad_id': unidad.pk if unidad is not None else None,
            }
        if rol == 'admin' and puesto == 'director':
            colegio_id = admin.colegio_id
            if colegio_id is None and unidad is not None:
                colegio_id = unidad.colegio_id
            if colegio_id is None:
                raise ErrorAlcanceInstitucional('El director no tiene un colegio asignado.')
            if unidad is not None and unidad.colegio_id != colegio_id:
                raise ErrorAlcanceInstitucional(
                    'La unidad heredada del director no pertenece a su colegio asignado.'
                )
            return {'tipo': 'COLEGIO', 'colegio_id': colegio_id, 'unidad_id': None}
        if puesto == 'secretaria':
            if unidad is None or unidad_admin is None:
                raise ErrorAlcanceInstitucional('La secretaría no tiene una unidad educativa asignada.')
            if admin.colegio_id is None or admin.colegio_id != unidad.colegio_id:
                raise ErrorAlcanceInstitucional(
                    'El colegio del perfil administrativo no coincide con la unidad asignada.'
                )
    elif hasattr(user, 'profesor'):
        unidad = unidad or user.profesor.unidad
    elif hasattr(user, 'estudiante'):
        unidad = unidad or user.estudiante.unidad

    if unidad is None:
        raise ErrorAlcanceInstitucional('El usuario no tiene una unidad educativa asignada.')
    if unidad.colegio_id is None:
        raise ErrorAlcanceInstitucional('La unidad educativa no tiene un colegio asociado.')

    rol = normalizar_nombre(getattr(getattr(user, 'rol', None), 'nombre', ''))
    if hasattr(user, 'admin'):
        tipo = 'UNIDAD'
    elif rol == 'profesor' or hasattr(user, 'profesor') or hasattr(user, 'estudiante'):
        tipo = 'PERSONAL'
    else:
        tipo = 'UNIDAD'
    return {
        'tipo': tipo,
        'colegio_id': unidad.colegio_id,
        'unidad_id': None if tipo == 'COLEGIO' else unidad.pk,
    }


def unidad_id_usuario(user):
    return resolver_alcance(user)['unidad_id']


def unidades_permitidas(user):
    alcance = resolver_alcance(user)
    if alcance['tipo'] == 'GLOBAL':
        return None
    if alcance['tipo'] == 'COLEGIO':
        from aplicaciones.institucion.models import UnidadEducativa
        return UnidadEducativa.objects.filter(
            colegio_id=alcance['colegio_id'],
        ).values_list('pk', flat=True)
    return [alcance['unidad_id']]


def validar_unidad(user, unidad):
    if unidad is None or unidad.colegio_id is None:
        raise ErrorAlcanceInstitucional('La unidad educativa no tiene un colegio asociado.')
    alcance = resolver_alcance(user)
    if alcance['tipo'] == 'GLOBAL':
        return
    if alcance['colegio_id'] != unidad.colegio_id:
        raise PermissionDenied('No puede acceder a otro colegio.')
    if alcance['tipo'] in {'UNIDAD', 'PERSONAL'} and alcance['unidad_id'] != unidad.pk:
        raise PermissionDenied('No puede acceder a otra unidad educativa.')


def serializar_alcance(user):
    alcance = resolver_alcance(user)
    colegio_nombre = unidad_nombre = None
    if alcance['colegio_id'] is not None:
        from aplicaciones.institucion.models import Colegio
        colegio_nombre = Colegio.objects.filter(pk=alcance['colegio_id']).values_list(
            'nombre', flat=True,
        ).first()
    if alcance['unidad_id'] is not None:
        from aplicaciones.institucion.models import UnidadEducativa
        unidad_nombre = UnidadEducativa.objects.filter(pk=alcance['unidad_id']).values_list(
            'nombre', flat=True,
        ).first()
    return {**alcance, 'colegio_nombre': colegio_nombre, 'unidad_nombre': unidad_nombre}

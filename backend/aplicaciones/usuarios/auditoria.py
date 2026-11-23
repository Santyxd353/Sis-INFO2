import hashlib
import hmac
import ipaddress
from collections.abc import Iterable
from datetime import datetime, timezone as datetime_timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone

from .models import EventoAuditoria
from .tenancy import ErrorAlcanceInstitucional


ACCIONES = {
    'LOGIN_EXITOSO', 'LOGIN_FALLIDO', 'TOKEN_RENOVADO', 'TOKEN_RECHAZADO', 'LOGOUT',
    'CREAR', 'ACTUALIZAR', 'DESACTIVAR', 'ELIMINAR', 'ARCHIVAR',
    'REPORTAR', 'EXPORTAR', 'DESCARGAR', 'CONSULTAR_QBE', 'ACTUALIZAR_DATASET', 'CONSULTAR_VOZ',
    'VOZ_INTERPRETAR', 'VOZ_EJECUTAR', 'VOZ_RECHAZAR',
}
ENTIDADES = {
    'COMUNICADO', 'LECTURA_COMUNICADO', 'ALERTA_COMUNICACION',
    'AUTENTICACION', 'USUARIO', 'INSCRIPCION', 'ASIGNACION_DOCENTE',
    'CONFIGURACION_EVALUACION', 'ACTIVIDAD_EVALUACION', 'CALIFICACION',
    'DOCUMENTO_ACADEMICO', 'PLAN', 'SUSCRIPCION', 'PAGO', 'INCIDENTE_DISCIPLINARIO',
    'CITACION_DISCIPLINARIA', 'CORRECCION_CALIFICACION',
    'HORARIO_CLASE', 'MATERIA', 'MATERIA_CURSO', 'MODULO_FISICO', 'AULA',
    'REPORTE_DEFINICION', 'REPORTE_EJECUCION',
    'ROL', 'PERMISO_ROL', 'PERMISO_COMPONENTE', 'ASIGNACION_ROLES', 'RESPALDO',
    'PLAN_PAGO', 'BECA', 'ASIGNACION_BECA', 'OBLIGACION_PAGO', 'PAGO_PENSION', 'SOLICITUD_QR',
}
_CAMPOS_PERMITIDOS = {
    'campos', 'metodo', 'resultado', 'motivo', 'estado_anterior', 'estado_nuevo', 'fuente', 'cantidad_filas',
}
_CLAVES_SENSIBLES = {
    'password', 'contrasena', 'contraseña', 'token', 'access', 'refresh', 'secret',
    'authorization', 'cookie', 'ci', 'documento', 'email', 'telefono', 'direccion',
}
_NOMBRES_CAMPO_SECRETOS = {
    'password', 'contrasena', 'contraseña', 'token', 'access', 'refresh',
    'secret', 'authorization', 'cookie',
}


def _identificador_enmascarado(valor):
    valor = str(valor or '').strip()
    if not valor:
        return 'credencial:no-informada'
    if '@' in valor:
        local, dominio = valor.split('@', 1)
        return f"credencial:{local[:2]}***@{dominio}"
    return f"credencial:{valor[:2]}***"


def _snapshot_actor(usuario=None, identificador=None):
    if usuario is not None and getattr(usuario, 'is_authenticated', False):
        # El historial muestra un identificador legible y estable; el ID
        # interno no se expone como ``usuario:<id>`` en la interfaz.
        return str(getattr(usuario, 'username', '') or usuario.pk)
    return _identificador_enmascarado(identificador)


def _ip_cliente(request):
    if request is None:
        return None
    remota = request.META.get('REMOTE_ADDR', '')
    proxies_confiables = getattr(settings, 'TRUSTED_PROXY_IPS', set())
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR', '')
    candidata = reenviada.split(',')[0].strip() if reenviada and remota in proxies_confiables else remota
    try:
        return str(ipaddress.ip_address(candidata)) if candidata else None
    except ValueError:
        return None


def _hash_ip(request):
    ip = _ip_cliente(request)
    if not ip:
        return None
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'), ip.encode('utf-8'), hashlib.sha256,
    ).hexdigest()


def sanitizar_cambios(cambios):
    if not cambios:
        return None
    if isinstance(cambios, Iterable) and not isinstance(cambios, (str, bytes, dict)):
        return {'campos': sorted({str(campo) for campo in cambios})}
    if not isinstance(cambios, dict):
        return None

    resultado = {}
    for clave, valor in cambios.items():
        clave_normalizada = str(clave).strip().lower()
        if clave_normalizada not in _CAMPOS_PERMITIDOS:
            continue
        if any(sensible in clave_normalizada for sensible in _CLAVES_SENSIBLES):
            continue
        if clave_normalizada == 'campos':
            campos = (
                valor if isinstance(valor, Iterable)
                and not isinstance(valor, (str, bytes, dict)) else []
            )
            resultado[clave_normalizada] = sorted({
                str(campo) for campo in campos
                if not any(s in str(campo).lower() for s in _NOMBRES_CAMPO_SECRETOS)
            })
        elif isinstance(valor, (str, int, float, bool)) or valor is None:
            resultado[clave_normalizada] = valor
    return resultado or None


def _correlacion_request(request):
    valor = getattr(request, 'audit_correlation_id', None) if request is not None else None
    if isinstance(valor, UUID):
        return valor
    try:
        return UUID(str(valor)) if valor else None
    except (TypeError, ValueError):
        return None


def _metadata_cliente(request):
    if request is None:
        return None, None
    fecha_raw = str(request.META.get('HTTP_X_CLIENT_TIME', '')).strip()
    zona_raw = str(request.META.get('HTTP_X_CLIENT_TIMEZONE', '')).strip()
    fecha_cliente = None
    zona_cliente = None
    if fecha_raw:
        try:
            fecha_cliente = datetime.fromisoformat(fecha_raw.replace('Z', '+00:00'))
            if timezone.is_naive(fecha_cliente):
                fecha_cliente = timezone.make_aware(fecha_cliente, datetime_timezone.utc)
        except ValueError:
            fecha_cliente = None
    if zona_raw and len(zona_raw) <= 64:
        try:
            ZoneInfo(zona_raw)
            zona_cliente = zona_raw
        except ZoneInfoNotFoundError:
            zona_cliente = None
    return fecha_cliente, zona_cliente


def registrar_evento(
    *, accion, entidad, request=None, usuario=None, entidad_id=None, cambios=None,
    colegio=None, unidad=None, identificador=None, correlacion=None, inferir_unidad=True,
):
    if accion not in ACCIONES:
        raise ValueError('Acción de auditoría no permitida.')
    if entidad not in ENTIDADES:
        raise ValueError('Entidad de auditoría no permitida.')

    usuario = usuario or getattr(request, 'user', None)
    if usuario is not None and not getattr(usuario, 'is_authenticated', False):
        usuario = None

    if inferir_unidad and unidad is None and usuario is not None:
        unidad = getattr(usuario, 'unidad', None)
        if unidad is None and hasattr(usuario, 'admin'):
            unidad = usuario.admin.unidad
    if colegio is None and unidad is not None:
        colegio = unidad.colegio

    if unidad is not None and colegio is None:
        raise ErrorAlcanceInstitucional(
            'No se puede auditar una operación institucional sin colegio.'
        )

    if unidad is not None and colegio is not None:
        ambito = EventoAuditoria.Ambito.UNIDAD
    elif colegio is not None:
        ambito = EventoAuditoria.Ambito.COLEGIO
    else:
        ambito = EventoAuditoria.Ambito.GLOBAL

    correlacion = correlacion or _correlacion_request(request)
    fecha_cliente, zona_cliente = _metadata_cliente(request)
    extra = {'correlacion': correlacion} if correlacion is not None else {}
    return EventoAuditoria.objects.create(
        ambito=ambito,
        colegio=colegio,
        unidad_educativa=unidad,
        usuario=usuario.pk if usuario is not None else None,
        actor_snapshot=_snapshot_actor(usuario, identificador),
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id) if entidad_id is not None else None,
        cambios_sanitizados=sanitizar_cambios(cambios),
        ip_hash=_hash_ip(request),
        fecha_cliente=fecha_cliente,
        zona_cliente=zona_cliente,
        **extra,
    )

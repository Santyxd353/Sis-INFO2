"""Reglas de negocio de suscripciones SaaS (HU-SE01).

El colegio constituye el tenant. La suscripción restringe qué módulos y
límites puede usar cada colegio; la validación se hace en el backend
(ocultar opciones en la interfaz no sustituye la autorización).
"""

from calendar import monthrange
from datetime import date

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import DIAS_PERIODICIDAD, Pago, Suscripcion


# Modelos siempre accesibles para un colegio (su propia facturación).
_MODELOS_FACTURACION = {'suscripcion', 'pago', 'plan'}


def calcular_vencimiento(fecha_inicio, periodicidad):
    meses = {'MENSUAL': 1, 'TRIMESTRAL': 3, 'SEMESTRAL': 6, 'ANUAL': 12}.get(periodicidad, 1)
    total = fecha_inicio.year * 12 + fecha_inicio.month - 1 + meses
    year, month_index = divmod(total, 12)
    return date(year, month_index + 1, min(fecha_inicio.day, monthrange(year, month_index + 1)[1]))


def colegio_del_usuario(user):
    """Devuelve el colegio (tenant) del usuario o None si no aplica.

    Un usuario sin colegio resuelto no está sujeto a restricciones de
    suscripción (SuperAdmin, datos incompletos, etc.).
    """
    if not getattr(user, 'is_authenticated', False):
        return None
    from aplicaciones.usuarios.tenancy import es_superadmin
    if es_superadmin(user):
        return None
    admin = getattr(user, 'admin', None)
    if admin is not None and admin.colegio_id:
        return admin.colegio_id
    unidad = getattr(user, 'unidad', None)
    if unidad is not None and unidad.colegio_id:
        return unidad.colegio_id
    if admin is not None and admin.unidad is not None:
        return admin.unidad.colegio_id
    return None


def suscripcion_activa(colegio):
    """Suscripción ACTIVA y no vencida del colegio (o None)."""
    colegio_id = getattr(colegio, 'pk', colegio)
    hoy = timezone.localdate()
    return (
        Suscripcion.objects
        .select_related('plan')
        .filter(
            colegio_id=colegio_id,
            estado=Suscripcion.Estado.ACTIVA,
            fecha_inicio__lte=hoy,
            fecha_vencimiento__gte=hoy,
        )
        .order_by('-fecha_vencimiento', '-id')
        .first()
    )


def suscripcion_mas_reciente(colegio):
    colegio_id = getattr(colegio, 'pk', colegio)
    return (
        Suscripcion.objects
        .select_related('plan')
        .filter(colegio_id=colegio_id)
        .order_by('-fecha_inicio', '-id')
        .first()
    )


def estado_efectivo(suscripcion):
    """Estado real de la suscripción considerando el vencimiento por fecha."""
    if suscripcion is None:
        return 'SIN_SUSCRIPCION'
    if (
        suscripcion.estado == Suscripcion.Estado.ACTIVA
        and suscripcion.fecha_vencimiento < timezone.localdate()
    ):
        return Suscripcion.Estado.VENCIDA
    return suscripcion.estado


def restriccion_activa(colegio):
    """Motivo (str) por el que el colegio está restringido, o None.

    Colegios sin ninguna suscripción contratada operan en modo prototipo sin
    restricciones; a partir de la primera suscripción se aplica la política.
    """
    colegio_id = getattr(colegio, 'pk', colegio)
    suscripcion = suscripcion_mas_reciente(colegio_id)
    if suscripcion is None:
        from aplicaciones.institucion.models import Colegio
        if Colegio.objects.filter(pk=colegio_id, requiere_suscripcion=True).exists():
            return 'El colegio debe contratar y pagar un plan para acceder a las funciones académicas.'
        return None
    if suscripcion_activa(colegio_id) is not None:
        return None
    estado = estado_efectivo(suscripcion)
    etiquetas = dict(Suscripcion.Estado.choices)
    return (
        f'La suscripción del colegio está en estado '
        f'"{etiquetas.get(estado, estado)}". Solo puede consultar el estado '
        f'de su suscripción y registrar pagos de renovación.'
    )


def autorizar_acceso_modelo(user, modelo):
    """Hook central de política de suscripciones para clases de permiso.

    - Sin suscripción contratada: sin restricción (modo prototipo).
    - Suscripción existente sin pago validado / vencida / suspendida /
      cancelada: restringe todas las funciones excepto facturación.
    - Suscripción activa: valida los módulos habilitados del plan.
    """
    from aplicaciones.usuarios.tenancy import es_superadmin
    if es_superadmin(user):
        return
    colegio_id = colegio_del_usuario(user)
    if colegio_id is None:
        return
    motivo = restriccion_activa(colegio_id)
    if motivo is not None:
        if modelo in _MODELOS_FACTURACION:
            return
        raise PermissionDenied(motivo)
    if not modelo or modelo in _MODELOS_FACTURACION:
        return
    activa = suscripcion_activa(colegio_id)
    modulos = list(activa.modulos_habilitados or []) if activa else []
    if modulos and modelo not in modulos:
        raise PermissionDenied(
            f'El módulo "{modelo}" no está habilitado en su plan vigente '
            f'({activa.plan.nombre}).'
        )


def contar_usuarios_colegio(colegio_id):
    from aplicaciones.usuarios.models import Usuario
    return Usuario.objects.filter(
        Q(unidad__colegio_id=colegio_id) | Q(admin__colegio_id=colegio_id),
    ).distinct().count()


def contar_unidades_colegio(colegio_id):
    from aplicaciones.institucion.models import UnidadEducativa
    return UnidadEducativa.objects.filter(colegio_id=colegio_id).count()


def validar_limite_usuarios(colegio, adicional=1):
    """Impide superar el límite de usuarios del plan vigente (regla 6)."""
    colegio_id = getattr(colegio, 'pk', colegio)
    if colegio_id is None:
        return
    activa = suscripcion_activa(colegio_id)
    if activa is None or activa.limite_usuarios <= 0:
        return
    actual = contar_usuarios_colegio(colegio_id)
    if actual + adicional > activa.limite_usuarios:
        raise ValidationError({
            'suscripcion': (
                f'Ha alcanzado el límite de {activa.limite_usuarios} usuarios '
                f'contratados en el plan "{activa.plan.nombre}". '
                f'Actualice su plan para dar de alta más usuarios.'
            ),
        })


def validar_limite_unidades(colegio, adicional=1):
    """Impide superar el límite de unidades educativas del plan vigente."""
    colegio_id = getattr(colegio, 'pk', colegio)
    if colegio_id is None:
        return
    activa = suscripcion_activa(colegio_id)
    if activa is None or activa.limite_unidades <= 0:
        return
    actual = contar_unidades_colegio(colegio_id)
    if actual + adicional > activa.limite_unidades:
        raise ValidationError({
            'suscripcion': (
                f'Ha alcanzado el límite de {activa.limite_unidades} unidades '
                f'educativas contratadas en el plan "{activa.plan.nombre}". '
                f'Actualice su plan para registrar más unidades.'
            ),
        })


def colegio_para_alta(datos):
    """Resuelve el colegio destino de una alta de usuario o unidad."""
    unidad = datos.get('unidad')
    if unidad is not None and getattr(unidad, 'colegio_id', None):
        return unidad.colegio_id
    unidad_id = datos.get('unidad_id')
    if unidad_id:
        from aplicaciones.institucion.models import UnidadEducativa
        return UnidadEducativa.objects.filter(pk=unidad_id).values_list(
            'colegio_id', flat=True,
        ).first()
    colegio = datos.get('colegio')
    if colegio is not None and getattr(colegio, 'pk', None):
        return colegio.pk
    colegio_id = datos.get('colegio_id')
    return colegio_id or None


def aplicar_pago_validado(pago):
    """Activa o renueva la suscripción asociada a un pago validado (regla 5).

    - PENDIENTE → ACTIVA (primera activación tras contratar).
    - VENCIDA   → renovación: se extiende la vigencia desde hoy (o desde la
      fecha de vencimiento si aún no se cumplió) más el periodo del plan.
    - SUSPENDIDA/CANCELADA no se modifican por un pago; la reactivación es
      una decisión explícita de la plataforma.
    """
    suscripcion = pago.suscripcion
    hoy = timezone.localdate()
    if suscripcion.estado == Suscripcion.Estado.PENDIENTE:
        suscripcion.estado = Suscripcion.Estado.ACTIVA
        if suscripcion.fecha_inicio < hoy:
            suscripcion.fecha_inicio = hoy
        suscripcion.fecha_vencimiento = calcular_vencimiento(suscripcion.fecha_inicio, suscripcion.periodicidad)
        suscripcion.save(update_fields=['estado', 'fecha_inicio', 'fecha_vencimiento', 'updated_at'])
        return suscripcion
    if suscripcion.estado == Suscripcion.Estado.ACTIVA and suscripcion.fecha_inicio > hoy:
        # Un pago validado no debe dejar bloqueado al colegio hasta una fecha
        # futura: esa fecha se usa para calendarios académicos, no para
        # retrasar el acceso ya autorizado por la plataforma.
        suscripcion.fecha_inicio = hoy
        suscripcion.save(update_fields=['fecha_inicio', 'updated_at'])
        return suscripcion
    if suscripcion.estado == Suscripcion.Estado.VENCIDA or (
        suscripcion.estado == Suscripcion.Estado.ACTIVA and suscripcion.fecha_vencimiento < hoy
    ):
        base = max(hoy, suscripcion.fecha_vencimiento)
        suscripcion.estado = Suscripcion.Estado.ACTIVA
        suscripcion.fecha_vencimiento = calcular_vencimiento(base, suscripcion.periodicidad)
        suscripcion.save(update_fields=['estado', 'fecha_vencimiento', 'updated_at'])
        return suscripcion
    return suscripcion


def marcar_pagos_vencidos():
    """Utilidad batch: marca como VENCIDAS las suscripciones ACTIVAS vencidas."""
    hoy = timezone.localdate()
    return Suscripcion.objects.filter(
        estado=Suscripcion.Estado.ACTIVA, fecha_vencimiento__lt=hoy,
    ).update(estado=Suscripcion.Estado.VENCIDA)


__all__ = [
    'aplicar_pago_validado', 'autorizar_acceso_modelo',
    'calcular_vencimiento', 'colegio_del_usuario', 'colegio_para_alta',
    'contar_usuarios_colegio', 'contar_unidades_colegio', 'estado_efectivo',
    'marcar_pagos_vencidos', 'restriccion_activa', 'suscripcion_activa',
    'suscripcion_mas_reciente', 'validar_limite_unidades',
    'validar_limite_usuarios',
]

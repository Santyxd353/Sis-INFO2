"""HU-25: cobro de cuotas por QR y su conciliación con la pasarela."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from . import pasarela, servicios
from .fechas import ZONA_BOLIVIA, hoy
from .models import ObligacionPago, Pago, SolicitudQR

VIGENCIA_QR = timedelta(minutes=30)
ESTADOS_PENDIENTE_PASARELA = ('PENDIENTE', 'PENDING')


def _expirar_vencidas(estudiante):
    SolicitudQR.objects.filter(
        estudiante=estudiante, estado=SolicitudQR.Estado.PENDIENTE, expira_at__lte=timezone.now(),
    ).update(estado=SolicitudQR.Estado.EXPIRADA, updated_at=timezone.now())


def crear_solicitud(usuario, estudiante, obligacion_ids=None):
    """Genera el QR por el saldo completo de las cuotas elegidas.

    Devuelve (solicitud, creada). Pedir de nuevo las mismas cuotas reutiliza el
    QR vigente en lugar de emitir otro cobro.
    """
    with transaction.atomic():
        cuotas = ObligacionPago.objects.select_for_update().select_related('cuota__plan').filter(
            estudiante=estudiante, estado=ObligacionPago.Estado.PENDIENTE,
        )
        if obligacion_ids:
            cuotas = cuotas.filter(pk__in=obligacion_ids)
        cuotas = [c for c in cuotas if c.saldo > 0]
        if obligacion_ids and len(cuotas) != len(set(obligacion_ids)):
            raise ValidationError({'obligaciones': 'Hay cuotas que no son del estudiante o que ya no tienen saldo.'})
        if not cuotas:
            raise ValidationError({'detail': 'El estudiante no tiene cuotas pendientes de pago.'})
        unidades = {c.cuota.plan.unidad_educativa_id for c in cuotas}
        if len(unidades) != 1:
            raise ValidationError({'obligaciones': 'Genere un QR por cada unidad educativa.'})

        _expirar_vencidas(estudiante)
        ids = {c.pk for c in cuotas}
        monto = sum(c.saldo for c in cuotas)
        for activa in SolicitudQR.objects.filter(
            estado=SolicitudQR.Estado.PENDIENTE, obligaciones__in=ids,
        ).distinct().prefetch_related('obligaciones'):
            if {o.pk for o in activa.obligaciones.all()} == ids and activa.monto == monto:
                return activa, False
            raise ValidationError({
                'detail': 'Ya hay un QR vigente que incluye alguna de esas cuotas. Páguelo, anúlelo o espere a que expire.',
            })

        solicitud = SolicitudQR.objects.create(
            unidad_educativa_id=unidades.pop(), estudiante=estudiante, monto=monto,
            expira_at=timezone.now() + VIGENCIA_QR, solicitado_por=usuario,
        )
        solicitud.obligaciones.set(ids)
        solicitud.qr_id, solicitud.qr_url = pasarela.generar(
            monto, f'PEN-{solicitud.pk}', solicitud.expira_at,
            colegio_id=solicitud.unidad_educativa.colegio_id,
        )
        solicitud.save(update_fields=['qr_id', 'qr_url', 'updated_at'])
    return solicitud, True


def _cobro_informado(data):
    """Extrae (monto, fecha) del cobro que informa la pasarela, o (None, None)."""
    pagos = data.get('payments')
    if not (isinstance(pagos, list) and len(pagos) == 1 and isinstance(pagos[0], dict)):
        return None, None
    try:
        monto = Decimal(str(pagos[0]['payment_amount']))
        fecha = parse_datetime(str(pagos[0]['payment_date']))
    except (KeyError, InvalidOperation, ValueError, TypeError):
        return None, None
    if not monto.is_finite() or fecha is None:
        return None, None
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, ZONA_BOLIVIA)
    return monto, fecha


def _observar(solicitud, motivo, monto=None):
    solicitud.estado = SolicitudQR.Estado.OBSERVADA
    solicitud.observacion = motivo
    solicitud.monto_reportado = monto


def verificar(solicitud_id, tardia=False):
    """Consulta la pasarela y, si confirma el cobro, registra el pago una sola vez.

    `tardia` (webhook) también revisa QR expirados o anulados: si la pasarela
    cobró igual, la solicitud queda observada para conciliación manual.
    """
    with transaction.atomic():
        solicitud = SolicitudQR.objects.select_for_update().get(pk=solicitud_id)
        fuera_de_plazo = solicitud.estado in (SolicitudQR.Estado.EXPIRADA, SolicitudQR.Estado.ANULADA)
        if solicitud.estado in (SolicitudQR.Estado.PAGADA, SolicitudQR.Estado.OBSERVADA) or (fuera_de_plazo and not tardia):
            return solicitud
        data = pasarela.consultar(solicitud.qr_id)
        estado = str(data.get('status', '')).strip().upper()
        if estado == 'PAGADO':
            monto, fecha = _cobro_informado(data)
            if monto is None:
                _observar(solicitud, 'La pasarela informó un cobro con datos ilegibles.')
            elif fuera_de_plazo:
                _observar(solicitud, 'La pasarela cobró un QR que ya estaba expirado o anulado.', monto)
            elif monto != solicitud.monto or fecha > solicitud.expira_at:
                _observar(solicitud, 'El monto o la fecha del cobro no coinciden con el QR emitido.', monto)
            else:
                try:
                    with transaction.atomic():
                        observacion = ('Cobro QR simulado, sin movimiento de dinero.' if pasarela.es_qr_simulado(solicitud.qr_id)
                                       else 'Cobro confirmado por la pasarela QR.')
                        solicitud.pago = servicios.registrar_pago(
                            usuario=solicitud.solicitado_por, estudiante=solicitud.estudiante, monto=monto,
                            metodo=Pago.Metodo.QR, fecha_pago=fecha.astimezone(ZONA_BOLIVIA).date(),
                            referencia=solicitud.qr_id, observaciones=observacion,
                            obligacion_ids=list(solicitud.obligaciones.values_list('pk', flat=True)),
                        )
                    solicitud.estado = SolicitudQR.Estado.PAGADA
                    solicitud.observacion = ''
                except ValidationError:
                    _observar(solicitud, 'La pasarela cobró, pero las cuotas ya no admiten el pago (¿se pagaron por otro medio?).', monto)
        elif estado in ESTADOS_PENDIENTE_PASARELA:
            if solicitud.estado == SolicitudQR.Estado.PENDIENTE and solicitud.expira_at <= timezone.now():
                solicitud.estado = SolicitudQR.Estado.EXPIRADA
        elif not fuera_de_plazo:
            _observar(solicitud, f'La pasarela devolvió un estado no reconocido: {estado[:40] or "vacío"}.')
        solicitud.verificado_at = timezone.now()
        solicitud.save()
    return solicitud


def procesar_notificacion(qr_id):
    """Webhook: devuelve True si el QR pertenece a pensiones y fue procesado."""
    solicitud = SolicitudQR.objects.filter(qr_id=qr_id).first()
    if solicitud is None:
        return False
    verificar(solicitud.pk, tardia=True)
    return True


def anular(solicitud_id, usuario, motivo):
    with transaction.atomic():
        solicitud = SolicitudQR.objects.select_for_update().get(pk=solicitud_id)
        if solicitud.estado != SolicitudQR.Estado.PENDIENTE:
            raise ValidationError({'detail': 'Solo se puede anular un QR pendiente de pago.'})
        solicitud.estado = SolicitudQR.Estado.ANULADA
        solicitud.observacion = motivo
        solicitud.resuelto_por = usuario
        solicitud.save(update_fields=['estado', 'observacion', 'resuelto_por', 'updated_at'])
    return solicitud


def resolver(solicitud_id, usuario, accion, motivo):
    """Conciliación manual de un QR observado: aplicar el cobro o descartarlo."""
    with transaction.atomic():
        solicitud = SolicitudQR.objects.select_for_update().get(pk=solicitud_id)
        if solicitud.estado != SolicitudQR.Estado.OBSERVADA:
            raise ValidationError({'detail': 'Solo se concilian manualmente los QR observados.'})
        if accion == 'aplicar':
            if not solicitud.monto_reportado:
                raise ValidationError({'detail': 'La pasarela no informó un monto cobrado que se pueda aplicar.'})
            solicitud.pago = servicios.registrar_pago(
                usuario=usuario, estudiante=solicitud.estudiante, monto=solicitud.monto_reportado,
                metodo=Pago.Metodo.QR, fecha_pago=hoy(), referencia=solicitud.qr_id or '',
                observaciones=f'Conciliación manual de QR: {motivo}',
            )
            solicitud.estado = SolicitudQR.Estado.PAGADA
        else:
            solicitud.estado = SolicitudQR.Estado.ANULADA
        solicitud.observacion = f'{solicitud.observacion} | Resuelto: {motivo}'.strip(' |')
        solicitud.resuelto_por = usuario
        solicitud.save()
    return solicitud


def estado_conciliacion(solicitud):
    if solicitud.estado == SolicitudQR.Estado.PAGADA:
        pago = solicitud.pago
        return 'CONCILIADA' if pago and pago.estado == Pago.Estado.VALIDO else 'DESCUADRE'
    return solicitud.estado


def resumen_conciliacion(solicitudes, pagos_qr):
    """Compara lo cobrado según la pasarela con lo registrado en el sistema."""
    cero = Decimal('0.00')
    pagadas = solicitudes.filter(estado=SolicitudQR.Estado.PAGADA)
    observadas = solicitudes.filter(estado=SolicitudQR.Estado.OBSERVADA)
    cobrado = (pagadas.aggregate(t=Sum('monto'))['t'] or cero) + (observadas.aggregate(t=Sum('monto_reportado'))['t'] or cero)
    registrado = pagadas.filter(pago__estado=Pago.Estado.VALIDO).aggregate(t=Sum('pago__monto'))['t'] or cero
    manuales = pagos_qr.filter(estado=Pago.Estado.VALIDO, solicitud_qr__isnull=True)
    return {
        'cobrado_pasarela': cobrado, 'registrado_sistema': registrado, 'diferencia': cobrado - registrado,
        'conciliadas': pagadas.filter(pago__estado=Pago.Estado.VALIDO).count(),
        'descuadres': pagadas.exclude(pago__estado=Pago.Estado.VALIDO).count(),
        'observadas': observadas.count(),
        'pendientes': solicitudes.filter(estado=SolicitudQR.Estado.PENDIENTE).count(),
        'expiradas': solicitudes.filter(estado=SolicitudQR.Estado.EXPIRADA).count(),
        'pagos_qr_sin_respaldo': manuales.count(),
        'monto_qr_sin_respaldo': manuales.aggregate(t=Sum('monto'))['t'] or cero,
    }

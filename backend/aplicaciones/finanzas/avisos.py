"""HU-28: alertas de pago a la familia (bandeja + push).

Todo vive dentro de finanzas: usa el modelo `Notificacion` existente sin
modificarlo y el envío push ya disponible en `usuarios.notificaciones`.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Sum

from aplicaciones.usuarios.models import Notificacion
from aplicaciones.usuarios.notificaciones import enviar_notificacion

from .fechas import hoy
from .models import ObligacionPago, RecordatorioPago

# Tipos de aviso de finanzas que se muestran en la bandeja de alertas de pago.
TIPOS_AVISO = ('PAGO', 'BECA', 'MOROSIDAD', 'RECORDATORIO_PAGO')


def familia_de(estudiante):
    """El estudiante y sus tutores: quienes deben enterarse de sus pagos."""
    return [estudiante.usuario_id, *estudiante.tutores.values_list('tutor__usuario_id', flat=True)]


def notificar(usuarios, tipo, titulo, mensaje, datos=None):
    """Deja el aviso en la bandeja de cada usuario (ids) y envía el push."""
    usuarios = [u for u in dict.fromkeys(usuarios) if u]
    if not usuarios:
        return []
    creadas = Notificacion.objects.bulk_create([
        Notificacion(usuario_id=usuario_id, tipo=tipo, titulo=titulo[:100], mensaje=mensaje)
        for usuario_id in usuarios
    ])
    enviar_notificacion(usuarios, titulo, mensaje[:180], datos={'tipo': tipo, **(datos or {})})
    return creadas


def _nombre(estudiante):
    return f'{estudiante.usuario.nombre} {estudiante.usuario.apellido}'.strip()


def _al_confirmar(estudiante, tipo, titulo, mensaje, datos):
    # Solo se avisa si la operación realmente quedó guardada.
    transaction.on_commit(
        lambda: notificar(familia_de(estudiante), tipo, titulo, mensaje, {'estudiante': estudiante.pk, **datos}),
    )


def avisar_pago(pago):
    _al_confirmar(
        pago.estudiante, 'PAGO', 'Pago registrado',
        f'Se registró el pago de Bs {pago.monto} de {_nombre(pago.estudiante)}. Recibo N.º {pago.numero_recibo:06d}.',
        {'pago': pago.pk},
    )


def avisar_pago_anulado(pago):
    _al_confirmar(
        pago.estudiante, 'PAGO', 'Pago anulado',
        f'El recibo N.º {pago.numero_recibo:06d} de {_nombre(pago.estudiante)} fue anulado. Las cuotas vuelven a estar pendientes.',
        {'pago': pago.pk},
    )


def avisar_beca(asignacion, revocada=False):
    estudiante = asignacion.estudiante
    if revocada:
        titulo, mensaje = 'Beca revocada', f'La beca "{asignacion.beca.nombre}" de {_nombre(estudiante)} fue revocada.'
    else:
        titulo, mensaje = (
            'Beca otorgada',
            f'{_nombre(estudiante)} recibió la beca "{asignacion.beca.nombre}". Sus cuotas pendientes ya reflejan el descuento.',
        )
    _al_confirmar(estudiante, 'BECA', titulo, mensaje, {'beca': asignacion.beca_id})


def enviar_recordatorios_pago(obligaciones, tipo, dias=5):
    """Avisa a cada familia sus cuotas vencidas (VENCIDAS) o por vencer (POR_VENCER).

    No repite el mismo tipo de recordatorio al mismo estudiante en el día:
    eso se controla con la tabla `finanzas_recordatorio_pago`.
    """
    fecha = hoy()
    pendientes = obligaciones.filter(estado=ObligacionPago.Estado.PENDIENTE, monto_final__gt=F('monto_pagado'))
    if tipo == RecordatorioPago.Tipo.VENCIDAS:
        pendientes = pendientes.filter(fecha_vencimiento__lt=fecha)
    else:
        pendientes = pendientes.filter(fecha_vencimiento__range=(fecha, fecha + timedelta(days=dias)))
    por_estudiante = list(
        pendientes.order_by().values('estudiante_id').annotate(total=Sum(F('monto_final') - F('monto_pagado'))),
    )
    from aplicaciones.estudiantes.models import Estudiante
    estudiantes = Estudiante.objects.select_related('usuario').in_bulk([f['estudiante_id'] for f in por_estudiante])
    tipo_aviso = 'MOROSIDAD' if tipo == RecordatorioPago.Tipo.VENCIDAS else 'RECORDATORIO_PAGO'
    enviados = omitidos = 0
    for fila in por_estudiante:
        estudiante = estudiantes[fila['estudiante_id']]
        total = Decimal(fila['total']).quantize(Decimal('0.01'))
        try:
            with transaction.atomic():
                RecordatorioPago.objects.create(estudiante=estudiante, tipo=tipo, fecha=fecha, monto=total)
        except IntegrityError:
            omitidos += 1
            continue
        nombre = _nombre(estudiante)
        if tipo == RecordatorioPago.Tipo.VENCIDAS:
            titulo = 'Cuotas vencidas'
            mensaje = f'{nombre} tiene cuotas vencidas por Bs {total}. Regularice el pago para evitar inconvenientes.'
        else:
            titulo = 'Cuota próxima a vencer'
            mensaje = f'{nombre} tiene cuotas por Bs {total} que vencen en los próximos {dias} días.'
        notificar(familia_de(estudiante), tipo_aviso, titulo, mensaje, {'estudiante': estudiante.pk})
        enviados += 1
    return {'estudiantes_avisados': enviados, 'ya_avisados_hoy': omitidos}

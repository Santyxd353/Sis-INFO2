"""Genera y confirma pagos de demostración para planes habilitados."""

from base64 import b64encode
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from reportlab.graphics.barcode import createBarcodeDrawing
from rest_framework.exceptions import ValidationError

from aplicaciones.usuarios.auditoria import registrar_evento

from . import stripe_checkout
from .models import MetodoPago, Pago, Suscripcion
from .servicios import aplicar_pago_validado, estado_efectivo


def plan_habilitado(plan_id, precio):
    return precio > 0 and str(plan_id) in settings.QR_DEMO_PLAN_IDS


def validar_plan(suscripcion):
    if not plan_habilitado(suscripcion.plan_id, suscripcion.precio_periodico) or not (
        MetodoPago.objects.filter(codigo=MetodoPago.Codigo.QR_SIMULADO, activo=True).exists()
    ):
        raise ValidationError('El QR simulado solo está disponible para los planes de demostración habilitados.')


def validar_intento(suscripcion):
    if estado_efectivo(suscripcion) not in (Suscripcion.Estado.PENDIENTE, Suscripcion.Estado.VENCIDA):
        raise ValidationError('La suscripción no está pendiente de pago o renovación.')
    pendientes = suscripcion.pagos.filter(resultado=Pago.Resultado.PENDIENTE)
    if pendientes.filter(metodo=Pago.Metodo.PASARELA, qr_expira_at__isnull=False).exists():
        raise ValidationError('Hay un cobro externo pendiente para esta suscripción.')
    stripe = pendientes.filter(metodo=Pago.Metodo.STRIPE).first()
    if stripe and (not stripe_checkout.modo_prueba() or not (stripe.stripe_session_id or '').startswith('cs_test_')):
        raise ValidationError('Hay un cobro de Stripe pendiente para esta suscripción.')
    return stripe


@transaction.atomic
def generar(suscripcion_id):
    suscripcion = Suscripcion.objects.select_for_update().get(pk=suscripcion_id)
    validar_plan(suscripcion)
    validar_intento(suscripcion)
    ahora = timezone.now()
    pendientes = suscripcion.pagos.filter(metodo=Pago.Metodo.QR_SIMULADO, resultado=Pago.Resultado.PENDIENTE)
    pendientes.filter(qr_expira_at__lte=ahora).update(
        resultado=Pago.Resultado.RECHAZADO, observacion='El QR simulado venció.', updated_at=ahora,
    )
    pago = pendientes.first()
    if pago:
        return pago, False
    pago = suscripcion.pagos.create(
        metodo=Pago.Metodo.QR_SIMULADO, referencia=f'DEMO-{uuid4().hex}',
        monto=suscripcion.precio_periodico, moneda=suscripcion.moneda,
        fecha=timezone.localdate(), qr_expira_at=ahora + timedelta(minutes=15),
        observacion='En espera de la confirmación simulada.',
    )
    return pago, True


def imagen(pago):
    codigo = createBarcodeDrawing('QR', value=f'EDUGESTION:SIMULADO:{pago.referencia}', width=210, height=210)
    svg = codigo.asString('svg').encode('utf-8')
    return 'data:image/svg+xml;base64,' + b64encode(svg).decode('ascii')


@transaction.atomic
def confirmar(pago, request):
    if pago.metodo != Pago.Metodo.QR_SIMULADO:
        raise ValidationError('Este pago no corresponde a un QR simulado.')
    suscripcion = Suscripcion.objects.select_for_update().get(pk=pago.suscripcion_id)
    pago = Pago.objects.select_for_update().get(pk=pago.pk)
    pago.suscripcion = suscripcion
    if pago.resultado == Pago.Resultado.VALIDADO:
        return pago
    validar_plan(suscripcion)
    pago_stripe = validar_intento(suscripcion)
    ahora = timezone.now()
    if pago.resultado != Pago.Resultado.PENDIENTE or not pago.qr_expira_at or pago.qr_expira_at <= ahora:
        raise ValidationError('El QR simulado venció. Genera uno nuevo desde la suscripción.')
    if pago.monto != suscripcion.precio_periodico or pago.moneda != suscripcion.moneda:
        raise ValidationError('El importe debe coincidir con la suscripción contratada.')
    if pago_stripe:
        stripe_checkout.cerrar_checkout_de_prueba(pago_stripe)
    pago.resultado = Pago.Resultado.VALIDADO
    pago.validado_por = request.user
    pago.validado_at = ahora
    pago.observacion = 'Pago simulado confirmado. Sin movimiento de dinero.'
    pago.save(update_fields=['resultado', 'validado_por', 'validado_at', 'observacion', 'updated_at'])
    aplicar_pago_validado(pago)
    registrar_evento(
        accion='ACTUALIZAR', entidad='PAGO', request=request, entidad_id=pago.pk,
        colegio=suscripcion.colegio, cambios={'resultado': pago.resultado, 'medio': pago.metodo},
    )
    return pago

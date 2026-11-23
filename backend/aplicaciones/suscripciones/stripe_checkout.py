"""Stripe Checkout para los pagos de vigencias institucionales."""
import logging
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import uuid4

import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from aplicaciones.usuarios.auditoria import registrar_evento
from .models import MetodoPago, Pago, Suscripcion
from .servicios import aplicar_pago_validado, estado_efectivo

logger = logging.getLogger(__name__)
EVENTOS_PAGADOS = {'checkout.session.completed', 'checkout.session.async_payment_succeeded'}
EVENTOS_FALLIDOS = {'checkout.session.expired', 'checkout.session.async_payment_failed'}
MONEDAS = {'BOB', 'USD'}


class StripeNoDisponible(APIException):
    status_code = 503
    default_detail = 'Stripe no está disponible en este momento. Puedes continuar el pago desde Suscripciones.'


def modo_prueba():
    return settings.STRIPE_SECRET_KEY.startswith(('sk_test_', 'rk_test_'))


def configurado():
    return (settings.STRIPE_SECRET_KEY.startswith(('sk_test_', 'rk_test_', 'sk_live_', 'rk_live_'))
            and settings.STRIPE_WEBHOOK_SECRET.startswith('whsec_'))


def habilitado():
    return configurado() and MetodoPago.objects.filter(codigo=MetodoPago.Codigo.STRIPE, activo=True).exists()


@transaction.atomic
def reservar_pago(suscripcion_id):
    suscripcion = Suscripcion.objects.select_for_update().get(pk=suscripcion_id)
    if estado_efectivo(suscripcion) not in (Suscripcion.Estado.PENDIENTE, Suscripcion.Estado.VENCIDA):
        raise ValidationError('La suscripción no está pendiente de pago o renovación.')
    if suscripcion.moneda not in MONEDAS or not 0 < suscripcion.precio_periodico < 1000000:
        raise ValidationError('El plan no tiene un monto o moneda admitidos para Stripe.')
    pendientes = suscripcion.pagos.filter(resultado=Pago.Resultado.PENDIENTE)
    if pendientes.filter(metodo=Pago.Metodo.PASARELA, qr_expira_at__isnull=False).exists():
        raise ValidationError('Existe un QR pendiente de conciliación para esta suscripción.')
    pago = pendientes.filter(metodo=Pago.Metodo.STRIPE).first()
    if pago:
        if not pago.stripe_session_id and pago.created_at < timezone.now() - timedelta(hours=23):
            raise ValidationError('Existe un intento de Stripe pendiente de conciliación.')
        return pago
    return Pago.objects.create(
        suscripcion=suscripcion, metodo=Pago.Metodo.STRIPE, referencia=f'STRIPE-{uuid4().hex}',
        monto=suscripcion.precio_periodico, moneda=suscripcion.moneda, fecha=timezone.localdate(),
        observacion='Pago pendiente de confirmación de Stripe.',
    )


def _obtener_sesion(sesiones, pago):
    if pago.stripe_session_id:
        return sesiones.retrieve(pago.stripe_session_id).to_dict()
    ruta = f'{settings.FRONTEND_PUBLIC_URL}/dashboard/suscripciones'
    sesion = sesiones.create({
        'mode': 'payment',
        'adaptive_pricing': {'enabled': False},
        'client_reference_id': pago.referencia,
        'metadata': {'aplicacion': 'gestion-escolar', 'pago': str(pago.pk)},
        'success_url': f'{ruta}?stripe=confirmacion',
        'cancel_url': f'{ruta}?stripe=cancelado',
        'line_items': [{
            'quantity': 1,
            'price_data': {
                'currency': pago.moneda.lower(), 'unit_amount': int(pago.monto * 100),
                'product_data': {'name': f'Suscripción EduGestión {pago.suscripcion.periodicidad.lower()}'},
            },
        }],
    }, options={'idempotency_key': pago.referencia}).to_dict()
    session_id = sesion.get('id', '')
    if not isinstance(session_id, str) or not session_id.startswith('cs_') or len(session_id) > 255:
        raise StripeNoDisponible()
    actualizado = Pago.objects.filter(pk=pago.pk, resultado=Pago.Resultado.PENDIENTE).filter(
        Q(stripe_session_id=None) | Q(stripe_session_id=session_id)
    ).update(stripe_session_id=session_id, updated_at=timezone.now())
    if not actualizado:
        raise ValidationError('El intento de pago cambió. Consulta el estado de la suscripción.')
    pago.stripe_session_id = session_id
    return sesion


def iniciar_checkout(suscripcion_id):
    if not habilitado():
        raise StripeNoDisponible()
    cliente = stripe.StripeClient(
        settings.STRIPE_SECRET_KEY, http_client=stripe.RequestsClient(timeout=(3, 10)),
    )
    sesiones = cliente.v1.checkout.sessions
    pago = reservar_pago(suscripcion_id)
    try:
        sesion = _obtener_sesion(sesiones, pago)
        if sesion.get('status') == 'expired':
            Pago.objects.filter(pk=pago.pk, resultado=Pago.Resultado.PENDIENTE).update(
                resultado=Pago.Resultado.RECHAZADO, observacion='Sesión de Stripe vencida.',
                updated_at=timezone.now(),
            )
            pago = reservar_pago(suscripcion_id)
            sesion = _obtener_sesion(sesiones, pago)
    except stripe.StripeError as exc:
        logger.warning('Stripe Checkout no respondió correctamente (%s).', type(exc).__name__)
        raise StripeNoDisponible() from exc
    if sesion.get('status') == 'complete':
        raise ValidationError('Stripe ya recibió este pago. Consulta el estado de la suscripción.')
    url = sesion.get('url') or ''
    destino = urlsplit(url)
    if sesion.get('status') != 'open' or destino.scheme != 'https' or destino.netloc != 'checkout.stripe.com':
        raise StripeNoDisponible()
    return {'checkout_url': url, 'pago': pago.pk}


def cerrar_checkout_de_prueba(pago):
    """Cierra un Checkout de prueba antes de cambiar al QR simulado."""
    if not configurado() or not modo_prueba() or not (pago.stripe_session_id or '').startswith('cs_test_'):
        raise ValidationError('Hay un cobro de Stripe pendiente para esta suscripción.')
    cliente = stripe.StripeClient(
        settings.STRIPE_SECRET_KEY, http_client=stripe.RequestsClient(timeout=(3, 5)), max_network_retries=0,
    )
    sesiones = cliente.v1.checkout.sessions
    try:
        sesion = sesiones.retrieve(pago.stripe_session_id)
        if sesion.livemode is not False or sesion.client_reference_id != pago.referencia:
            raise ValidationError('El intento de Stripe no se pudo conciliar con la suscripción.')
        if sesion.status == 'open' and sesion.payment_status == 'unpaid':
            sesion = sesiones.expire(pago.stripe_session_id)
    except stripe.StripeError as exc:
        raise StripeNoDisponible() from exc
    if sesion.status != 'expired' or sesion.payment_status != 'unpaid':
        raise ValidationError('Stripe ya recibió este intento. Espera su confirmación antes de cambiar de método.')
    pago.resultado = Pago.Resultado.RECHAZADO
    pago.observacion = 'Checkout de prueba cerrado al elegir un pago QR simulado.'
    pago.save(update_fields=['resultado', 'observacion', 'updated_at'])


def obtener_evento(cuerpo, firma):
    if not configurado():
        raise StripeNoDisponible()
    try:
        return stripe.Webhook.construct_event(cuerpo, firma, settings.STRIPE_WEBHOOK_SECRET).to_dict()
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise ValidationError('Firma de Stripe inválida.') from exc


def procesar_evento(evento, request):
    tipo = evento.get('type')
    if tipo not in EVENTOS_PAGADOS | EVENTOS_FALLIDOS:
        return
    if evento.get('livemode') is not (not modo_prueba()):
        raise ValidationError('El modo de pago recibido no corresponde a esta configuración.')
    sesion = (evento.get('data') or {}).get('object') or {}
    metadata = sesion.get('metadata') or {}
    if metadata.get('aplicacion') != 'gestion-escolar':
        return
    pago_id = metadata.get('pago', '')
    if not isinstance(pago_id, str) or not pago_id.isascii() or not pago_id.isdigit() or len(pago_id) > 18:
        raise ValidationError('Identificador de pago inválido.')
    referencia = sesion.get('client_reference_id')
    pagos = Pago.objects.filter(pk=int(pago_id), metodo=Pago.Metodo.STRIPE, referencia=referencia)
    suscripcion_id = pagos.values_list('suscripcion_id', flat=True).first()
    if suscripcion_id is None:
        return
    with transaction.atomic():
        suscripcion = Suscripcion.objects.select_for_update().get(pk=suscripcion_id)
        pago = pagos.select_for_update().get()
        if not pago.stripe_session_id:
            # Stripe puede reintentar si la sesión todavía se está registrando.
            raise StripeNoDisponible()
        if (sesion.get('id') != pago.stripe_session_id or sesion.get('mode') != 'payment'
                or sesion.get('currency') != pago.moneda.lower()
                or sesion.get('amount_total') != int(pago.monto * 100)):
            raise ValidationError('La sesión o el monto no coinciden con el pago registrado.')
        if pago.resultado != Pago.Resultado.PENDIENTE:
            return
        if tipo in EVENTOS_PAGADOS:
            if sesion.get('payment_status') != 'paid':
                return
            pago.resultado = Pago.Resultado.VALIDADO
            pago.validado_at = timezone.now()
            pago.observacion = 'Pago confirmado por Stripe.'
            pago.suscripcion = suscripcion
            aplicar_pago_validado(pago)
        else:
            pago.resultado = Pago.Resultado.RECHAZADO
            pago.observacion = 'La sesión de Stripe venció o el pago falló.'
        pago.save(update_fields=['resultado', 'validado_at', 'observacion', 'updated_at'])
        registrar_evento(
            accion='ACTUALIZAR', entidad='PAGO', request=request, colegio=suscripcion.colegio,
            entidad_id=pago.pk, cambios={'resultado': pago.resultado, 'medio': 'STRIPE'},
        )

import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from .models import Pago, Suscripcion
from .tests_hu_se01 import BaseSuscripcionesTests


@override_settings(STRIPE_SECRET_KEY='sk_test_local', STRIPE_WEBHOOK_SECRET='whsec_local')
class StripeCheckoutTests(BaseSuscripcionesTests):
    def setUp(self):
        hoy = timezone.localdate()
        self.suscripcion = Suscripcion.objects.create(
            colegio=self.colegio_a, plan=self.plan_basico, precio_periodico='100.00',
            moneda='BOB', periodicidad='MENSUAL', fecha_inicio=hoy,
            fecha_vencimiento=hoy + timedelta(days=30),
        )
        self.checkout = f'{self.api}/suscripciones/{self.suscripcion.pk}/checkout-stripe/'
        self.webhook = f'{self.api}/stripe/webhook/'

    @patch('aplicaciones.suscripciones.stripe_checkout.stripe.StripeClient')
    def test_checkout_es_institucional_y_reutiliza_sesion(self, cliente):
        sesiones = cliente.return_value.v1.checkout.sessions
        sesion = {'id': 'cs_test_edu', 'status': 'open', 'url': 'https://checkout.stripe.com/c/pay/cs_test_edu'}
        sesiones.create.return_value.to_dict.return_value = sesion
        sesiones.retrieve.return_value.to_dict.return_value = sesion
        self.client.force_authenticate(self.director_b)
        self.assertEqual(self.client.post(self.checkout, {}, format='json').status_code, 404)
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.post(self.checkout, {}, format='json')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['checkout_url'], sesion['url'])
        self.assertEqual(self.client.post(self.checkout, {}, format='json').status_code, 200)
        pago = Pago.objects.get(suscripcion=self.suscripcion)
        parametros = sesiones.create.call_args.args[0]
        self.assertEqual(parametros['mode'], 'payment')
        self.assertEqual(parametros['line_items'][0]['price_data']['unit_amount'], 10000)
        self.assertEqual(parametros['line_items'][0]['price_data']['currency'], 'bob')
        self.assertEqual(sesiones.create.call_args.kwargs['options']['idempotency_key'], pago.referencia)
        sesiones.create.assert_called_once()
        sesiones.retrieve.assert_called_once_with(sesion['id'])
        self.assertEqual(pago.resultado, Pago.Resultado.PENDIENTE)
        self.suscripcion.refresh_from_db()
        self.assertEqual(self.suscripcion.estado, Suscripcion.Estado.PENDIENTE)

    def notificar(self, sesion, *, firma_correcta=True, livemode=False, tipo='checkout.session.completed'):
        evento = {
            'id': 'evt_edu', 'object': 'event', 'type': tipo, 'livemode': livemode,
            'data': {'object': sesion},
        }
        cuerpo = json.dumps(evento, separators=(',', ':'))
        instante = int(timezone.now().timestamp())
        secreto = b'whsec_local' if firma_correcta else b'whsec_incorrecto'
        firma = hmac.new(secreto, f'{instante}.{cuerpo}'.encode(), hashlib.sha256).hexdigest()
        return self.client.post(self.webhook, cuerpo, content_type='application/json',
                                HTTP_STRIPE_SIGNATURE=f't={instante},v1={firma}')

    def test_webhook_requiere_firma_estado_monto_y_es_idempotente(self):
        pago = Pago.objects.create(suscripcion=self.suscripcion, metodo=Pago.Metodo.STRIPE,
            referencia='referencia-verificada', monto='100.00', moneda='BOB', fecha=timezone.localdate(),
            stripe_session_id='cs_test_edu')
        sesion = {
            'id': pago.stripe_session_id, 'object': 'checkout.session', 'mode': 'payment',
            'metadata': {'aplicacion': 'gestion-escolar', 'pago': str(pago.pk)},
            'client_reference_id': pago.referencia, 'currency': 'bob',
            'amount_total': 10000, 'payment_status': 'paid',
        }
        self.assertEqual(self.notificar(sesion, firma_correcta=False).status_code, 400)
        self.assertEqual(self.notificar(sesion, livemode=True).status_code, 400)
        self.assertEqual(self.notificar({**sesion, 'amount_total': 9999}).status_code, 400)
        self.assertEqual(self.notificar({**sesion, 'id': 'cs_test_other'}).status_code, 400)
        self.assertEqual(self.notificar({**sesion, 'payment_status': 'unpaid'}).status_code, 204)
        pago.refresh_from_db()
        self.assertEqual(pago.resultado, Pago.Resultado.PENDIENTE)
        self.assertEqual(self.notificar(sesion).status_code, 204)
        pago.refresh_from_db()
        self.suscripcion.refresh_from_db()
        self.assertEqual(pago.resultado, Pago.Resultado.VALIDADO)
        self.assertEqual(self.suscripcion.estado, Suscripcion.Estado.ACTIVA)
        validado_at = pago.validado_at
        self.assertEqual(self.notificar(sesion).status_code, 204)
        pago.refresh_from_db()
        self.assertEqual(pago.validado_at, validado_at)

    def test_rechaza_validacion_manual_y_oculta_stripe_sin_claves(self):
        pago = Pago.objects.create(suscripcion=self.suscripcion, metodo=Pago.Metodo.STRIPE,
            referencia='manual', monto='100.00', moneda='BOB', fecha=timezone.localdate())
        self.client.force_authenticate(self.superusuario)
        self.assertEqual(self.client.post(f'{self.api}/pagos/{pago.pk}/validar/').status_code, 400)
        self.assertEqual(self.client.post(f'{self.api}/pagos/{pago.pk}/rechazar/').status_code, 400)
        with override_settings(STRIPE_SECRET_KEY='', STRIPE_WEBHOOK_SECRET=''):
            respuesta = self.client.get(f'{self.api}/metodos-pago-publicos/')
            self.assertEqual(respuesta.status_code, 200)
            self.assertNotIn('STRIPE', {item['codigo'] for item in respuesta.data})
            self.assertEqual(self.client.post(self.checkout, {}, format='json').status_code, 503)

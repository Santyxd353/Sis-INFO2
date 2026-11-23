from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.utils import timezone

from .models import Pago, Suscripcion
from .tests_hu_se01 import BaseSuscripcionesTests


class QrSimuladoTests(BaseSuscripcionesTests):
    def setUp(self):
        self.client.force_authenticate(self.director_a)
        fecha = timezone.localdate()
        self.suscripcion = Suscripcion.objects.create(
            colegio=self.colegio_a, plan=self.plan_basico,
            precio_periodico=self.plan_basico.precio, periodicidad='MENSUAL',
            fecha_inicio=fecha, fecha_vencimiento=fecha + timedelta(days=30),
        )
        self.generar = f'{self.api}/suscripciones/{self.suscripcion.pk}/generar-qr-simulado/'

    def test_activa_solo_al_simular_y_respeta_el_alcance_del_colegio(self):
        with self.settings(QR_DEMO_PLAN_IDS=[str(self.plan_basico.pk)]):
            respuesta = self.client.post(self.generar)
            self.assertEqual(respuesta.status_code, 201, respuesta.content[:400])
            self.assertTrue(respuesta.data['qr_imagen_simulada'].startswith('data:image/'))
            self.assertEqual(self.client.post(self.generar).data['id'], respuesta.data['id'])
            self.suscripcion.refresh_from_db()
            self.assertEqual(self.suscripcion.estado, 'PENDIENTE')

            confirmar = f"{self.api}/pagos/{respuesta.data['id']}/simular-pago-qr/"
            self.client.force_authenticate(self.director_b)
            self.assertEqual(self.client.post(confirmar).status_code, 404)
            self.client.force_authenticate(self.director_a)
            for _ in range(2):
                pago = self.client.post(confirmar)
                self.assertEqual(pago.status_code, 200, pago.data)
                self.assertEqual(pago.data['resultado'], 'VALIDADO')
            self.suscripcion.refresh_from_db()
            self.assertEqual(self.suscripcion.estado, 'ACTIVA')
            self.assertEqual(self.suscripcion.pagos.count(), 1)

    def test_fuera_del_plan_demo_o_con_cobro_externo_pendiente(self):
        with self.settings(QR_DEMO_PLAN_IDS=[]):
            self.assertEqual(self.client.post(self.generar).status_code, 400)
        Pago.objects.create(
            suscripcion=self.suscripcion, metodo=Pago.Metodo.STRIPE,
            monto=self.suscripcion.precio_periodico, moneda=self.suscripcion.moneda,
            fecha=timezone.localdate(), referencia='stripe-pendiente',
        )
        with self.settings(QR_DEMO_PLAN_IDS=[str(self.plan_basico.pk)]):
            self.assertEqual(self.client.post(self.generar).status_code, 400)
        self.assertEqual(self.suscripcion.pagos.count(), 1)

    @patch('aplicaciones.suscripciones.stripe_checkout.stripe.StripeClient')
    def test_cambiar_desde_stripe_de_prueba_solo_si_el_checkout_sigue_impago(self, cliente):
        pago_stripe = Pago.objects.create(
            suscripcion=self.suscripcion, metodo=Pago.Metodo.STRIPE,
            monto=self.suscripcion.precio_periodico, moneda=self.suscripcion.moneda,
            fecha=timezone.localdate(), referencia='stripe-demo', stripe_session_id='cs_test_demo',
        )
        sesiones = cliente.return_value.v1.checkout.sessions
        sesion = SimpleNamespace(
            livemode=False, client_reference_id=pago_stripe.referencia, status='complete', payment_status='paid',
        )
        sesiones.retrieve.return_value = sesion
        sesiones.expire.return_value = SimpleNamespace(status='expired', payment_status='unpaid')
        with self.settings(QR_DEMO_PLAN_IDS=[str(self.plan_basico.pk)],
                           STRIPE_SECRET_KEY='sk_test_local', STRIPE_WEBHOOK_SECRET='whsec_local'):
            creado = self.client.post(self.generar)
            self.assertEqual(creado.status_code, 201, creado.data)
            sesiones.retrieve.assert_not_called()
            confirmar = f"{self.api}/pagos/{creado.data['id']}/simular-pago-qr/"
            self.assertEqual(self.client.post(confirmar).status_code, 400)
            sesiones.expire.assert_not_called()
            self.suscripcion.refresh_from_db()
            self.assertEqual(self.suscripcion.estado, 'PENDIENTE')

            sesion.status, sesion.payment_status = 'open', 'unpaid'
            self.assertEqual(self.client.post(confirmar).status_code, 200)
            sesiones.expire.assert_called_once_with(pago_stripe.stripe_session_id)
        pago_stripe.refresh_from_db()
        self.assertEqual(pago_stripe.resultado, 'RECHAZADO')

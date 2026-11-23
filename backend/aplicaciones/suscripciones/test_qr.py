from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.utils import timezone

from .models import Pago, Suscripcion
from .tests_hu_se01 import BaseSuscripcionesTests


@override_settings(VENDIS_ENV='sandbox', VENDIS_API_BASE_URL='https://qr-dev.cobranza.emizor.com',
                   VENDIS_API_KEY='test', VENDIS_BUSINESS_CODE='123', VENDIS_WEBHOOK_TOKEN='t' * 32)
class QrTests(BaseSuscripcionesTests):
    def setUp(self):
        self.client.force_authenticate(self.superusuario)
        today = timezone.localdate()
        self.suscripcion = Suscripcion.objects.create(
            colegio=self.colegio_a, plan=self.plan_basico, precio_periodico=Decimal('100.00'),
            periodicidad='MENSUAL', fecha_inicio=today, fecha_vencimiento=today + timedelta(days=30))

    @patch('aplicaciones.suscripciones.vendis.generar', return_value=('qr-123', 'https://example.com/qr.png'))
    def test_qr_paid_only_after_verified_and_idempotent(self, generar):
        url = f'{self.api}/suscripciones/{self.suscripcion.pk}/generar-qr/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 200)
        generar.assert_called_once()
        pago = Pago.objects.get(pk=response.data['id'])
        self.assertEqual(pago.resultado, 'PENDIENTE')
        self.suscripcion.refresh_from_db()
        self.assertEqual(self.suscripcion.estado, 'PENDIENTE')
        date = timezone.now().astimezone(ZoneInfo('America/La_Paz')).strftime('%Y-%m-%d %H:%M:%S')
        with patch('aplicaciones.suscripciones.vendis.consultar', return_value={
            'status': 'PAGADO', 'payments': [{'payment_amount': '100.00', 'payment_date': date}],
        }):
            url = f'{self.api}/pagos/{pago.pk}/consultar-qr/'
            self.assertEqual(self.client.post(url).status_code, 200)
            self.assertEqual(self.client.post(url).status_code, 200)
        pago.refresh_from_db()
        self.suscripcion.refresh_from_db()
        self.assertEqual(pago.resultado, 'VALIDADO')
        self.assertEqual(self.suscripcion.estado, 'ACTIVA')

    def test_manual_gateway_cannot_auto_approve(self):
        response = self.client.post(f'{self.api}/pagos/', {
            'suscripcion': self.suscripcion.pk, 'metodo': 'PASARELA',
            'referencia': 'falsa', 'monto': '100.00',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Pago.objects.filter(suscripcion=self.suscripcion).exists())

    @patch('aplicaciones.suscripciones.vendis.generar', return_value=('qr-other', 'https://example.com/qr.png'))
    def test_other_tenant_cannot_access_qr(self, generar):
        self.client.force_authenticate(self.director_b)
        response = self.client.post(f'{self.api}/suscripciones/{self.suscripcion.pk}/generar-qr/')
        self.assertEqual(response.status_code, 404)
        generar.assert_not_called()

    def test_public_catalog_hides_inactive_plans(self):
        self.client.force_authenticate(None)
        response = self.client.get(f'{self.api}/planes-publicos/')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', []) if isinstance(response.data, dict) else response.data
        self.assertNotIn(self.plan_inactivo.pk, [row['id'] for row in data])

    @patch('aplicaciones.suscripciones.vendis.consultar')
    def test_webhook_requires_token_and_verifies_with_provider(self, consultar):
        pago = Pago.objects.create(suscripcion=self.suscripcion, metodo='PASARELA', referencia='webhook',
            monto=Decimal('100'), moneda='BOB', fecha=timezone.localdate(), qr_id='webhook-qr',
            qr_expira_at=timezone.now() + timedelta(minutes=10))
        url = f'{self.api}/vendis/webhook/'
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(url, {'qr_id': pago.qr_id}, format='json').status_code, 403)
        consultar.assert_not_called()
        date = timezone.now().astimezone(ZoneInfo('America/La_Paz')).strftime('%Y-%m-%d %H:%M:%S')
        consultar.return_value = {'status': 'PAGADO', 'payments': [{'payment_amount': '100.00', 'payment_date': date}]}
        for _ in range(2):
            response = self.client.post(url, {'qr_id': pago.qr_id}, format='json', HTTP_AUTHORIZATION='Bearer ' + 't' * 32)
            self.assertEqual(response.status_code, 200, response.data)
        consultar.assert_called_once()
        pago.refresh_from_db()
        self.assertEqual(pago.resultado, 'VALIDADO')

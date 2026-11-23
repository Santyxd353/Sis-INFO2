from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .fechas import ZONA_BOLIVIA
from .models import Pago, SolicitudQR
from .tests import ConCuotasAsignadas, PAGOS

SOLICITUDES = '/api/finanzas/solicitudes-qr/'
CONCILIACION = '/api/finanzas/conciliacion-qr/'
WEBHOOK = '/api/suscripciones/vendis/webhook/'
GENERAR = 'aplicaciones.finanzas.pasarela.generar'
CONSULTAR = 'aplicaciones.finanzas.pasarela.consultar'


def cobro(monto):
    fecha = timezone.now().astimezone(ZONA_BOLIVIA).strftime('%Y-%m-%d %H:%M:%S')
    return {'status': 'PAGADO', 'payments': [{'payment_amount': str(monto), 'payment_date': fecha}]}


class PagoQRBase(ConCuotasAsignadas):
    def setUp(self):
        super().setUp()
        self.tutor = APIClient()
        self.tutor.force_authenticate(self.tutor_user)
        parche = patch(GENERAR, side_effect=lambda monto, ref, venc, *, colegio_id: (
            f'qr-{ref}', 'https://pasarela.example/qr.png',
        ))
        self.generar = parche.start()
        self.addCleanup(parche.stop)

    def solicitar(self, cuotas=None, cliente=None):
        datos = {'estudiante': self.student.pk}
        if cuotas:
            datos['obligaciones'] = [c.pk for c in cuotas]
        return (cliente or self.tutor).post(SOLICITUDES, datos, format='json')

    def verificar(self, solicitud_id, respuesta_pasarela, cliente=None):
        with patch(CONSULTAR, return_value=respuesta_pasarela):
            return (cliente or self.tutor).post(f'{SOLICITUDES}{solicitud_id}/verificar/')


class PagoQRHU25Tests(PagoQRBase):
    def test_tutor_genera_qr_y_repetir_reutiliza_el_vigente(self):
        primera = self.solicitar([self.c1, self.c2])
        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual((primera.data['monto'], primera.data['estado']), ('666.66', 'PENDIENTE'))
        self.assertEqual(len(primera.data['conceptos']), 2)
        segunda = self.solicitar([self.c2, self.c1])
        self.assertEqual((segunda.status_code, segunda.data['id']), (200, primera.data['id']))
        self.generar.assert_called_once()

    def test_cobro_confirmado_registra_el_pago_una_sola_vez(self):
        solicitud = self.solicitar([self.c1]).data
        self.assertEqual(self.verificar(solicitud['id'], {'status': 'PENDIENTE'}).data['estado'], 'PENDIENTE')
        pagada = self.verificar(solicitud['id'], cobro('333.33'))
        self.assertEqual((pagada.data['estado'], pagada.data['conciliacion'], pagada.data['numero_recibo']), ('PAGADA', 'CONCILIADA', 1))
        self.verificar(solicitud['id'], cobro('333.33'))
        pago = Pago.objects.get()
        self.assertEqual((pago.metodo, pago.monto, pago.referencia), ('QR', Decimal('333.33'), solicitud['qr_id']))
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.estado, 'PAGADA')

    def test_monto_distinto_queda_observado_y_se_concilia_a_mano(self):
        solicitud = self.solicitar([self.c1]).data
        observada = self.verificar(solicitud['id'], cobro('300.00'))
        self.assertEqual((observada.data['estado'], observada.data['monto_reportado']), ('OBSERVADA', '300.00'))
        self.assertFalse(Pago.objects.exists())
        resolver = f"{SOLICITUDES}{solicitud['id']}/resolver/"
        self.assertEqual(self.tutor.post(resolver, {'accion': 'aplicar', 'motivo': 'x'}, format='json').status_code, 403)
        aplicada = self.client.post(resolver, {'accion': 'aplicar', 'motivo': 'Verificado en extracto'}, format='json')
        self.assertEqual(aplicada.data['estado'], 'PAGADA')
        self.c1.refresh_from_db()
        self.assertEqual((self.c1.monto_pagado, self.c1.estado), (Decimal('300.00'), 'PENDIENTE'))

    def test_cuota_pagada_por_otro_medio_antes_de_confirmar(self):
        solicitud = self.solicitar([self.c1]).data
        self.pagar('333.33')
        observada = self.verificar(solicitud['id'], cobro('333.33'))
        self.assertEqual(observada.data['estado'], 'OBSERVADA')
        self.assertEqual(Pago.objects.count(), 1)
        descartada = self.client.post(
            f"{SOLICITUDES}{solicitud['id']}/resolver/", {'accion': 'descartar', 'motivo': 'Se devolvió al tutor'}, format='json',
        )
        self.assertEqual(descartada.data['estado'], 'ANULADA')

    def test_no_emite_dos_qr_para_la_misma_cuota_hasta_anular(self):
        solicitud = self.solicitar([self.c1]).data
        self.assertEqual(self.solicitar([self.c1, self.c2]).status_code, 400)
        anulada = self.tutor.post(f"{SOLICITUDES}{solicitud['id']}/anular/", {'motivo': 'Me equivoqué'}, format='json')
        self.assertEqual(anulada.data['estado'], 'ANULADA')
        self.assertEqual(self.solicitar([self.c1, self.c2]).status_code, 201)

    def test_qr_expirado_y_cobro_tardio_por_webhook(self):
        solicitud = self.solicitar([self.c1]).data
        SolicitudQR.objects.filter(pk=solicitud['id']).update(expira_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.verificar(solicitud['id'], {'status': 'PENDIENTE'}).data['estado'], 'EXPIRADA')
        anonimo = APIClient()
        with override_settings(VENDIS_WEBHOOK_TOKEN='t' * 32), patch(CONSULTAR, return_value=cobro('333.33')):
            self.assertEqual(anonimo.post(WEBHOOK, {'qr_id': solicitud['qr_id']}, format='json').status_code, 403)
            respuesta = anonimo.post(WEBHOOK, {'qr_id': solicitud['qr_id']}, format='json', HTTP_AUTHORIZATION='Bearer ' + 't' * 32)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(SolicitudQR.objects.get(pk=solicitud['id']).estado, 'OBSERVADA')
        self.assertFalse(Pago.objects.exists())

    def test_webhook_confirma_un_qr_vigente(self):
        solicitud = self.solicitar().data
        with override_settings(VENDIS_WEBHOOK_TOKEN='t' * 32), patch(CONSULTAR, return_value=cobro('1000.00')):
            APIClient().post(WEBHOOK, {'qr_id': solicitud['qr_id']}, format='json', HTTP_AUTHORIZATION='Bearer ' + 't' * 32)
        self.assertEqual(SolicitudQR.objects.get(pk=solicitud['id']).estado, 'PAGADA')
        self.assertTrue(all(o.estado == 'PAGADA' for o in self.obligaciones()))

    def test_solo_la_familia_o_la_administracion_del_estudiante(self):
        for usuario, esperado in ((self.outsider, 404), (self.teacher, 403)):
            cliente = APIClient()
            cliente.force_authenticate(usuario)
            self.assertEqual(self.solicitar(cliente=cliente).status_code, esperado)
        self.assertEqual(self.solicitar(cliente=self.client).status_code, 201)
        ajeno = APIClient()
        ajeno.force_authenticate(self.outsider)
        self.assertEqual(ajeno.get(SOLICITUDES).data['count'], 0)
        self.assertEqual(self.tutor.get(SOLICITUDES).data['count'], 1)

    def test_conciliacion_detecta_descuadres(self):
        solicitud = self.solicitar([self.c1]).data
        pagada = self.verificar(solicitud['id'], cobro('333.33')).data
        resumen = self.client.get(CONCILIACION, {'unidad_educativa': self.unit.pk}).data
        self.assertEqual((resumen['resumen']['conciliadas'], resumen['resumen']['diferencia'], resumen['por_resolver']),
                         (1, Decimal('0.00'), []))
        self.client.post(f"{PAGOS}{pagada['pago']}/anular/", {'motivo': 'Error'}, format='json')
        self.pagar('10.00', metodo='QR', referencia='manual-1')
        datos = self.client.get(CONCILIACION).data
        self.assertEqual((datos['resumen']['descuadres'], datos['resumen']['diferencia'], datos['resumen']['pagos_qr_sin_respaldo']),
                         (1, Decimal('333.33'), 1))
        self.assertEqual(datos['por_resolver'][0]['conciliacion'], 'DESCUADRE')
        self.assertEqual(self.tutor.get(CONCILIACION).status_code, 403)


class ModoSimuladoTests(ConCuotasAsignadas):
    def test_colegio_demo_puede_simular_con_debug_apagado(self):
        with override_settings(DEBUG=False, FINANZAS_QR_DEMO_COLEGIO_IDS=[self.school.pk]):
            solicitud = self.client.post(SOLICITUDES, {
                'estudiante': self.student.pk, 'obligaciones': [self.c1.pk],
            }, format='json')
            self.assertEqual(solicitud.status_code, 201, solicitud.data)
            self.assertTrue(solicitud.data['simulado'])
            imagen = APIClient().get(solicitud.data['qr_url'].replace('http://testserver', ''))
            self.assertEqual((imagen.status_code, imagen['Cache-Control']), (200, 'no-store'))
            confirmar = f"{SOLICITUDES}{solicitud.data['id']}/simular-cobro/"
            with override_settings(FINANZAS_QR_DEMO_COLEGIO_IDS=[self.other_unit.colegio_id]):
                self.assertEqual(self.client.post(confirmar).status_code, 403)
            self.assertEqual(self.client.post(confirmar).data['estado'], 'PAGADA')

    def test_flujo_completo_sin_credenciales(self):
        tutor = APIClient()
        tutor.force_authenticate(self.tutor_user)
        with override_settings(DEBUG=True, VENDIS_ENV='simulado'):
            solicitud = tutor.post(SOLICITUDES, {'estudiante': self.student.pk, 'obligaciones': [self.c1.pk]}, format='json').data
            self.assertTrue(solicitud['qr_url'].startswith('http://testserver/api/finanzas/qr-simulado/SIM-'))
            imagen = APIClient().get(solicitud['qr_url'].replace('http://testserver', ''))
            self.assertEqual((imagen.status_code, imagen['Content-Type']), (200, 'image/png'))
            simular = f"{SOLICITUDES}{solicitud['id']}/simular-cobro/"
            self.assertEqual(tutor.post(simular).status_code, 403)
            self.assertEqual(self.client.post(simular).data['estado'], 'PAGADA')
            self.assertTrue(self.client.get(CONCILIACION).data['modo_simulado'])

    def test_simulacion_inexistente_fuera_del_modo_de_pruebas(self):
        solicitud = SolicitudQR.objects.create(
            unidad_educativa=self.unit, estudiante=self.student, monto=Decimal('10'), qr_id='SIM-x',
            expira_at=timezone.now() + timedelta(minutes=5),
        )
        self.assertEqual(self.client.post(f'{SOLICITUDES}{solicitud.pk}/simular-cobro/').status_code, 403)
        self.assertEqual(APIClient().get('/api/finanzas/qr-simulado/SIM-x.png').status_code, 404)
        with override_settings(DEBUG=False, VENDIS_ENV='simulado'):
            self.assertEqual(APIClient().get('/api/finanzas/qr-simulado/SIM-x.png').status_code, 404)

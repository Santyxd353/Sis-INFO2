from io import StringIO

from django.core.management import call_command
from rest_framework.test import APIClient

from aplicaciones.usuarios.models import EventoAuditoria, Notificacion, PermisoPuesto, Puesto

from .models import RecordatorioPago
from .tests import ConCuotasAsignadas

RECORDATORIOS = '/api/finanzas/recordatorios-pago/'
AVISOS = '/api/finanzas/avisos/'


def cliente_de(usuario):
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    return cliente


class AlertasPagoHU28Tests(ConCuotasAsignadas):
    def avisos(self, tipo):
        return Notificacion.objects.filter(tipo=tipo)

    def test_recordatorio_de_cuotas_vencidas_sin_repetir_en_el_dia(self):
        primero = self.client.post(RECORDATORIOS, {'tipo': 'VENCIDAS'}, format='json')
        self.assertEqual(primero.data['estudiantes_avisados'], 1)
        avisos = self.avisos('MOROSIDAD')
        self.assertEqual(set(avisos.values_list('usuario_id', flat=True)), {self.student_user.pk, self.tutor_user.pk})
        self.assertIn('666.66', avisos.first().mensaje)
        repetido = self.client.post(RECORDATORIOS, {'tipo': 'VENCIDAS'}, format='json')
        self.assertEqual((repetido.data['estudiantes_avisados'], repetido.data['ya_avisados_hoy']), (0, 1))
        self.assertEqual(avisos.count(), 2)
        self.assertEqual(RecordatorioPago.objects.count(), 1)
        self.assertTrue(EventoAuditoria.objects.filter(entidad='OBLIGACION_PAGO', accion='REPORTAR').exists())
        historial = self.client.get(RECORDATORIOS).data
        self.assertEqual((historial[0]['tipo'], historial[0]['monto']), ('VENCIDAS', '666.66'))

    def test_recordatorio_de_cuotas_por_vencer(self):
        self.assertEqual(self.client.post(RECORDATORIOS, {'tipo': 'POR_VENCER', 'dias': 5}, format='json').data['estudiantes_avisados'], 0)
        self.assertEqual(self.client.post(RECORDATORIOS, {'tipo': 'POR_VENCER', 'dias': 30}, format='json').data['estudiantes_avisados'], 1)
        self.assertIn('333.34', self.avisos('RECORDATORIO_PAGO').first().mensaje)

    def test_solo_administrativos_envian_recordatorios(self):
        for usuario in (self.tutor_user, self.teacher):
            self.assertEqual(cliente_de(usuario).post(RECORDATORIOS, {'tipo': 'VENCIDAS'}, format='json').status_code, 403)
        self.assertEqual(cliente_de(self.outsider).post(RECORDATORIOS, {'tipo': 'VENCIDAS'}, format='json').data['estudiantes_avisados'], 0)

    def test_pagos_y_becas_avisan_a_la_familia(self):
        with self.captureOnCommitCallbacks(execute=True):
            pago = self.pagar('100.00').data
        self.assertEqual(set(self.avisos('PAGO').values_list('usuario_id', flat=True)), {self.student_user.pk, self.tutor_user.pk})
        self.assertIn('000001', self.avisos('PAGO').first().mensaje)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/finanzas/pagos/{pago['id']}/anular/", {'motivo': 'Error'}, format='json')
            self.otorgar(self.crear_beca())
        self.assertTrue(self.avisos('PAGO').filter(titulo='Pago anulado').exists())
        self.assertEqual(self.avisos('BECA').count(), 2)

    def test_bandeja_de_avisos_solo_muestra_lo_propio_de_finanzas(self):
        Notificacion.objects.create(usuario=self.tutor_user, tipo='BOLETIN', titulo='Boletín', mensaje='x')
        with self.captureOnCommitCallbacks(execute=True):
            self.pagar('100.00')
        tutor = cliente_de(self.tutor_user)
        self.assertEqual(tutor.get(f'{AVISOS}resumen/').data['no_leidas'], 1)
        aviso = tutor.get(AVISOS, {'leida': 'false'}).data['results'][0]
        self.assertEqual(aviso['tipo'], 'PAGO')
        self.assertEqual(cliente_de(self.student_user).post(f"{AVISOS}{aviso['id']}/leer/").status_code, 404)
        self.assertTrue(tutor.post(f"{AVISOS}{aviso['id']}/leer/").data['leida'])
        self.assertEqual(cliente_de(self.student_user).post(f'{AVISOS}leer-todas/').data['marcadas'], 1)
        # El aviso de otro módulo no se toca.
        self.assertFalse(Notificacion.objects.get(tipo='BOLETIN').leida)

    def test_comando_programable(self):
        salida = StringIO()
        call_command('enviar_recordatorios_pago', '--dias', '30', stdout=salida)
        self.assertIn('VENCIDAS: 1 avisados', salida.getvalue())
        self.assertIn('POR_VENCER: 1 avisados', salida.getvalue())

    def test_tesoreria_no_recibe_permisos_implicitos_de_finanzas(self):
        # Tesorería obtiene finanzas mediante un rol funcional, no por su puesto.
        tesoreria = Puesto.objects.filter(nombre='Tesorería').first()
        self.assertFalse(PermisoPuesto.objects.filter(puesto=tesoreria, modelo__nombre='alerta-pago').exists())
        directores = PermisoPuesto.objects.filter(puesto__nombre='Director', modelo__nombre='alerta-pago')
        self.assertEqual(set(directores.values_list('accion__nombre', flat=True)), {'listar', 'crear'})

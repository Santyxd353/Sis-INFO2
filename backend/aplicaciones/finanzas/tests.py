from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import EventoAuditoria

from .fechas import hoy
from .models import AsignacionBeca, Beca, ObligacionPago, PlanPago
from .servicios import dividir_monto

PLANES = '/api/finanzas/planes-pago/'
BECAS = '/api/finanzas/becas/'
ASIGNACIONES = '/api/finanzas/asignaciones-beca/'
OBLIGACIONES = '/api/finanzas/obligaciones/'
PAGOS = '/api/finanzas/pagos/'
ESTADO_CUENTA = '/api/finanzas/estado-cuenta/'
MOROSIDAD = '/api/finanzas/morosidad/'
SIMULACION = '/api/finanzas/simulacion-tributaria/'


class FinanzasBase(SchoolFixture, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.director)

    def crear_plan(self, **extra):
        datos = {
            'unidad_educativa': self.unit.pk, 'calendario_academico': self.calendar.pk,
            'nombre': 'Pensión 2026', 'monto_total': '1000.00', 'numero_cuotas': 3, **extra,
        }
        respuesta = self.client.post(PLANES, datos, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return respuesta.data['id']

    def plan_activo(self, **extra):
        plan_id = self.crear_plan(**extra)
        respuesta = self.client.post(
            f'{PLANES}{plan_id}/generar-cuotas/', {'fecha_primer_vencimiento': '2026-02-10'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self.client.post(f'{PLANES}{plan_id}/activar/').status_code, 200)
        return plan_id

    def crear_beca(self, tipo='PORCENTAJE', valor='50.00', nombre='Excelencia'):
        respuesta = self.client.post(BECAS, {
            'unidad_educativa': self.unit.pk, 'nombre': nombre, 'tipo_descuento': tipo, 'valor': valor,
        }, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return respuesta.data['id']

    def otorgar(self, beca_id):
        return self.client.post(ASIGNACIONES, {
            'beca': beca_id, 'estudiante': self.student.pk,
            'calendario_academico': self.calendar.pk, 'motivo': 'Mejor promedio',
        }, format='json')

    def obligaciones(self):
        return ObligacionPago.objects.filter(estudiante=self.student).order_by('cuota__numero')


class PlanPagoHU22Tests(FinanzasBase):
    def test_divide_monto_y_la_ultima_cuota_absorbe_el_redondeo(self):
        self.assertEqual(dividir_monto(Decimal('1000.00'), 3), [Decimal('333.33'), Decimal('333.33'), Decimal('333.34')])

    def test_genera_cuotas_mensuales_con_concepto(self):
        plan_id = self.crear_plan()
        respuesta = self.client.post(
            f'{PLANES}{plan_id}/generar-cuotas/', {'fecha_primer_vencimiento': '2026-01-31'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 200)
        cuotas = respuesta.data['cuotas']
        self.assertEqual([c['fecha_vencimiento'] for c in cuotas], ['2026-01-31', '2026-02-28', '2026-03-31'])
        self.assertEqual(cuotas[1]['concepto'], 'Cuota 2 - Febrero')
        self.assertTrue(EventoAuditoria.objects.filter(entidad='PLAN_PAGO', accion='CREAR').exists())

    def test_fecha_fuera_de_la_gestion_es_rechazada(self):
        plan_id = self.crear_plan()
        respuesta = self.client.post(
            f'{PLANES}{plan_id}/generar-cuotas/', {'fecha_primer_vencimiento': '2027-02-01'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_no_activa_sin_cuotas(self):
        plan_id = self.crear_plan()
        self.assertEqual(self.client.post(f'{PLANES}{plan_id}/activar/').status_code, 400)

    def test_plan_activo_solo_permite_editar_nombre_y_descripcion(self):
        plan_id = self.plan_activo()
        self.assertEqual(self.client.patch(f'{PLANES}{plan_id}/', {'monto_total': '2000.00'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'{PLANES}{plan_id}/', {'nombre': 'Pensión anual'}, format='json').status_code, 200)
        self.assertEqual(
            self.client.post(f'{PLANES}{plan_id}/generar-cuotas/', {'fecha_primer_vencimiento': '2026-02-10'}, format='json').status_code,
            400,
        )

    def test_asignar_por_curso_genera_obligaciones_de_forma_idempotente(self):
        plan_id = self.plan_activo()
        primera = self.client.post(f'{PLANES}{plan_id}/asignar/', {'curso': self.course.pk}, format='json')
        self.assertEqual(primera.status_code, 200)
        self.assertEqual(primera.data['obligaciones_creadas'], 3)
        segunda = self.client.post(f'{PLANES}{plan_id}/asignar/', {'estudiantes': [self.student.pk]}, format='json')
        self.assertEqual((segunda.data['obligaciones_creadas'], segunda.data['obligaciones_existentes']), (0, 3))
        self.assertEqual(self.obligaciones().count(), 3)
        self.assertEqual(self.client.get(f'{PLANES}{plan_id}/').data['estudiantes_asignados'], 1)

    def test_no_asigna_planes_en_borrador_ni_de_otro_nivel(self):
        borrador = self.crear_plan(nombre='Borrador')
        self.assertEqual(self.client.post(f'{PLANES}{borrador}/asignar/', {'curso': self.course.pk}, format='json').status_code, 400)
        secundaria = self.plan_activo(nombre='Secundaria', nivel_educativo='SEC')
        respuesta = self.client.post(f'{PLANES}{secundaria}/asignar/', {'estudiantes': [self.student.pk, 99999]}, format='json')
        self.assertEqual(respuesta.data['obligaciones_creadas'], 0)
        self.assertEqual(len(respuesta.data['rechazados']), 2)

    def test_desactivar_conserva_las_obligaciones(self):
        plan_id = self.plan_activo()
        self.client.post(f'{PLANES}{plan_id}/asignar/', {'curso': self.course.pk}, format='json')
        self.assertEqual(self.client.post(f'{PLANES}{plan_id}/desactivar/').data['estado'], 'INACTIVO')
        self.assertEqual(self.obligaciones().count(), 3)


class BecasHU23Tests(FinanzasBase):
    def test_beca_porcentual_se_aplica_al_asignar_el_plan(self):
        self.assertEqual(self.otorgar(self.crear_beca()).status_code, 201)
        plan_id = self.plan_activo()
        self.client.post(f'{PLANES}{plan_id}/asignar/', {'curso': self.course.pk}, format='json')
        primera = self.obligaciones().first()
        self.assertEqual((primera.descuento, primera.monto_final), (Decimal('166.67'), Decimal('166.66')))

    def test_monto_fijo_nunca_supera_la_cuota(self):
        self.otorgar(self.crear_beca('MONTO_FIJO', '500.00', 'Hermanos'))
        plan_id = self.plan_activo()
        self.client.post(f'{PLANES}{plan_id}/asignar/', {'curso': self.course.pk}, format='json')
        self.assertTrue(all(o.monto_final == 0 and o.estado == 'PAGADA' for o in self.obligaciones()))
        asignacion = AsignacionBeca.objects.get()
        self.client.post(f'{ASIGNACIONES}{asignacion.pk}/revocar/', {'motivo': 'Fin del beneficio'}, format='json')
        self.assertTrue(all(o.estado == 'PENDIENTE' and o.monto_final > 0 for o in self.obligaciones()))

    def test_otorgar_y_revocar_recalcula_solo_pendientes(self):
        plan_id = self.plan_activo()
        self.client.post(f'{PLANES}{plan_id}/asignar/', {'curso': self.course.pk}, format='json')
        pagada = self.obligaciones().first()
        self.client.post(PAGOS, {
            'estudiante': self.student.pk, 'monto': str(pagada.monto_final), 'metodo': 'EFECTIVO',
        }, format='json')

        asignacion = self.otorgar(self.crear_beca(valor='10.00'))
        self.assertEqual(asignacion.status_code, 201)
        descuentos = [o.descuento for o in self.obligaciones()]
        self.assertEqual(descuentos, [Decimal('0.00'), Decimal('33.33'), Decimal('33.33')])

        revocada = self.client.post(f"{ASIGNACIONES}{asignacion.data['id']}/revocar/", {'motivo': 'Bajo rendimiento'}, format='json')
        self.assertEqual(revocada.data['estado'], 'REVOCADA')
        self.assertTrue(all(o.descuento == 0 for o in self.obligaciones()))

    def test_una_sola_beca_vigente_por_gestion(self):
        self.otorgar(self.crear_beca())
        self.assertEqual(self.otorgar(self.crear_beca(nombre='Deportiva')).status_code, 400)

    def test_porcentaje_mayor_a_cien_y_beca_inactiva_son_rechazados(self):
        respuesta = self.client.post(BECAS, {
            'unidad_educativa': self.unit.pk, 'nombre': 'Mal', 'tipo_descuento': 'PORCENTAJE', 'valor': '120',
        }, format='json')
        self.assertEqual(respuesta.status_code, 400)
        beca_id = self.crear_beca()
        self.client.post(f'{BECAS}{beca_id}/desactivar/')
        self.assertEqual(self.otorgar(beca_id).status_code, 400)

    def test_no_cambia_descuento_de_beca_con_asignaciones_vigentes(self):
        beca_id = self.crear_beca()
        self.otorgar(beca_id)
        self.assertEqual(self.client.patch(f'{BECAS}{beca_id}/', {'valor': '80'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'{BECAS}{beca_id}/', {'descripcion': 'Promedio > 90'}, format='json').status_code, 200)


class ObligacionesYAlcanceTests(FinanzasBase):
    def setUp(self):
        super().setUp()
        plan_id = self.plan_activo()
        self.client.post(f'{PLANES}{plan_id}/asignar/', {'curso': self.course.pk}, format='json')
        self.plan_id = plan_id

    def test_anular_solo_pendientes(self):
        obligacion = self.obligaciones().first()
        sin_motivo = self.client.post(f'{OBLIGACIONES}{obligacion.pk}/anular/', {'motivo': ' '}, format='json')
        self.assertEqual(sin_motivo.status_code, 400)
        anulada = self.client.post(f'{OBLIGACIONES}{obligacion.pk}/anular/', {'motivo': 'Retiro'}, format='json')
        self.assertEqual(anulada.data['estado'], 'ANULADA')
        self.assertEqual(self.client.post(f'{OBLIGACIONES}{obligacion.pk}/anular/', {'motivo': 'x'}, format='json').status_code, 400)

    def test_filtro_de_vencidas(self):
        self.obligaciones().update(fecha_vencimiento=hoy() + timedelta(days=30))
        ObligacionPago.objects.filter(pk=self.obligaciones().first().pk).update(
            fecha_vencimiento=hoy() - timedelta(days=1),
        )
        respuesta = self.client.get(OBLIGACIONES, {'vencidas': 'true'})
        self.assertEqual(respuesta.data['count'], 1)
        self.assertTrue(respuesta.data['results'][0]['vencida'])

    def test_tutor_ve_las_obligaciones_de_su_estudiante_sin_modificarlas(self):
        tutor = APIClient()
        tutor.force_authenticate(self.tutor_user)
        self.assertEqual(tutor.get(OBLIGACIONES).data['count'], 3)
        obligacion = self.obligaciones().first()
        self.assertEqual(tutor.post(f'{OBLIGACIONES}{obligacion.pk}/anular/', {'motivo': 'x'}, format='json').status_code, 403)
        self.assertEqual(tutor.get(PLANES).status_code, 403)

    def test_estudiante_ve_las_suyas_y_profesor_no_tiene_acceso(self):
        estudiante = APIClient()
        estudiante.force_authenticate(self.student_user)
        self.assertEqual(estudiante.get(OBLIGACIONES).data['count'], 3)
        profesor = APIClient()
        profesor.force_authenticate(self.teacher)
        self.assertEqual(profesor.get(OBLIGACIONES).status_code, 403)

    def test_director_de_otro_colegio_no_accede(self):
        ajeno = APIClient()
        ajeno.force_authenticate(self.outsider)
        self.assertEqual(ajeno.get(PLANES).data['count'], 0)
        self.assertEqual(ajeno.get(f'{PLANES}{self.plan_id}/').status_code, 404)
        self.assertEqual(ajeno.get(OBLIGACIONES).data['count'], 0)
        crear = ajeno.post(PLANES, {
            'unidad_educativa': self.unit.pk, 'calendario_academico': self.calendar.pk,
            'nombre': 'Intruso', 'monto_total': '10', 'numero_cuotas': 1,
        }, format='json')
        self.assertEqual(crear.status_code, 403)
        self.assertFalse(PlanPago.objects.filter(nombre='Intruso').exists())

    def test_buscador_de_estudiantes_respeta_el_alcance(self):
        respuesta = self.client.get(f'{ASIGNACIONES}estudiantes/', {'buscar': 'student'})
        self.assertEqual([e['id'] for e in respuesta.data], [self.student.pk])
        ajeno = APIClient()
        ajeno.force_authenticate(self.outsider)
        self.assertEqual(ajeno.get(f'{ASIGNACIONES}estudiantes/').data, [])
        self.assertFalse(AsignacionBeca.objects.exists())
        self.assertFalse(Beca.objects.exists())


class ConCuotasAsignadas(FinanzasBase):
    """Plan de 1000 Bs en 3 cuotas asignado; las fechas se fijan relativas a hoy."""

    def setUp(self):
        super().setUp()
        plan_id = self.plan_activo()
        self.client.post(f'{PLANES}{plan_id}/asignar/', {'curso': self.course.pk}, format='json')
        fecha_hoy = hoy()
        for obligacion, dias in zip(self.obligaciones(), (-40, -10, 20)):
            ObligacionPago.objects.filter(pk=obligacion.pk).update(fecha_vencimiento=fecha_hoy + timedelta(days=dias))
        self.c1, self.c2, self.c3 = self.obligaciones()

    def pagar(self, monto, cliente=None, **extra):
        return (cliente or self.client).post(PAGOS, {
            'estudiante': self.student.pk, 'monto': monto, 'metodo': 'EFECTIVO', **extra,
        }, format='json')


class PagosHU24Tests(ConCuotasAsignadas):
    def test_pago_parcial_se_aplica_desde_la_cuota_mas_antigua(self):
        respuesta = self.pagar('500.00')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data['numero_recibo'], 1)
        self.assertEqual([d['monto'] for d in respuesta.data['detalles']], ['333.33', '166.67'])
        self.c1.refresh_from_db(); self.c2.refresh_from_db()
        self.assertEqual((self.c1.estado, self.c2.estado, self.c2.saldo), ('PAGADA', 'PENDIENTE', Decimal('166.66')))
        self.assertEqual(self.pagar('10.00').data['numero_recibo'], 2)
        self.assertTrue(EventoAuditoria.objects.filter(entidad='PAGO_PENSION', accion='CREAR').exists())

    def test_pago_dirigido_a_cuotas_especificas(self):
        respuesta = self.pagar('333.34', obligaciones=[self.c3.pk])
        self.assertEqual(respuesta.status_code, 201)
        self.c3.refresh_from_db(); self.c1.refresh_from_db()
        self.assertEqual((self.c3.estado, self.c1.estado), ('PAGADA', 'PENDIENTE'))

    def test_validaciones_del_pago(self):
        self.assertEqual(self.pagar('1000.01').status_code, 400)
        self.assertEqual(self.pagar('10', metodo='TRANSFERENCIA').status_code, 400)
        manana = (hoy() + timedelta(days=1)).isoformat()
        self.assertEqual(self.pagar('10', fecha_pago=manana).status_code, 400)
        self.pagar('333.33')
        self.assertEqual(self.pagar('10', obligaciones=[self.c1.pk]).status_code, 400)

    def test_anular_pago_restituye_saldos_y_bloquea_anular_cuotas_con_pagos(self):
        pago = self.pagar('500.00').data
        self.assertEqual(self.client.post(f'{OBLIGACIONES}{self.c2.pk}/anular/', {'motivo': 'x'}, format='json').status_code, 400)
        anulado = self.client.post(f"{PAGOS}{pago['id']}/anular/", {'motivo': 'Error de caja'}, format='json')
        self.assertEqual(anulado.data['estado'], 'ANULADO')
        self.assertTrue(all(o.monto_pagado == 0 and o.estado == 'PENDIENTE' for o in self.obligaciones()))
        self.assertEqual(self.client.post(f"{PAGOS}{pago['id']}/anular/", {'motivo': 'otra vez'}, format='json').status_code, 400)

    def test_recibo_pdf(self):
        pago = self.pagar('500.00').data
        respuesta = self.client.get(f"{PAGOS}{pago['id']}/recibo/")
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertTrue(respuesta.content.startswith(b'%PDF'))

    def test_estado_de_cuenta(self):
        self.pagar('500.00')
        datos = self.client.get(ESTADO_CUENTA, {'estudiante': self.student.pk}).data
        resumen = datos['resumen']
        self.assertEqual((resumen['total_a_pagar'], resumen['total_pagado'], resumen['saldo_pendiente']),
                         (Decimal('1000.00'), Decimal('500.00'), Decimal('500.00')))
        self.assertEqual(resumen['saldo_vencido'], Decimal('166.66'))
        self.assertEqual(resumen['proximo_monto'], Decimal('333.34'))
        self.assertEqual((len(datos['obligaciones']), len(datos['pagos'])), (3, 1))

    def test_la_familia_consulta_pero_no_registra_pagos(self):
        self.pagar('100.00')
        tutor = APIClient()
        tutor.force_authenticate(self.tutor_user)
        self.assertEqual(tutor.get(PAGOS).data['count'], 1)
        self.assertEqual(tutor.get(ESTADO_CUENTA, {'estudiante': self.student.pk}).status_code, 200)
        self.assertEqual(self.pagar('10', cliente=tutor).status_code, 403)
        estudiante = APIClient()
        estudiante.force_authenticate(self.student_user)
        self.assertEqual(estudiante.get(ESTADO_CUENTA).data['estudiante'], self.student.pk)
        ajeno = APIClient()
        ajeno.force_authenticate(self.outsider)
        self.assertEqual(self.pagar('10', cliente=ajeno).status_code, 404)
        self.assertEqual(ajeno.get(ESTADO_CUENTA, {'estudiante': self.student.pk}).status_code, 404)


class MorosidadHU26Tests(ConCuotasAsignadas):
    def test_reporte_de_morosidad_por_tramos(self):
        datos = self.client.get(MOROSIDAD, {'unidad_educativa': self.unit.pk}).data
        fila = datos['estudiantes'][0]
        self.assertEqual((fila['cuotas_vencidas'], fila['monto_vencido'], fila['dias_mora'], fila['tramo']),
                         (2, Decimal('666.66'), 40, '31-60'))
        self.assertEqual(datos['resumen']['indice_morosidad'], Decimal('100.00'))
        self.assertEqual(self.client.get(MOROSIDAD, {'dias_minimos': 50}).data['estudiantes'], [])

    def test_pagar_lo_vencido_quita_al_estudiante_de_la_morosidad(self):
        self.pagar('666.66')
        datos = self.client.get(MOROSIDAD).data
        self.assertEqual((datos['resumen']['estudiantes_morosos'], datos['estudiantes']), (0, []))

    def test_simulacion_tributaria(self):
        self.pagar('1000.00')
        fecha_hoy = hoy()
        datos = self.client.get(SIMULACION, {
            'desde': (fecha_hoy - timedelta(days=5)).isoformat(), 'hasta': fecha_hoy.isoformat(), 'credito_fiscal': '20',
        }).data
        cobrado = datos['cobrado']
        self.assertEqual(
            (cobrado['debito_fiscal_iva'], cobrado['iva_a_pagar'], cobrado['it'], cobrado['total_impuestos'], cobrado['ingreso_neto']),
            (Decimal('130.00'), Decimal('110.00'), Decimal('30.00'), Decimal('140.00'), Decimal('860.00')),
        )
        self.assertEqual(len(datos['mensual']), 1)
        self.assertEqual(self.client.get(SIMULACION, {'desde': fecha_hoy.isoformat(), 'hasta': '2020-01-01'}).status_code, 400)

    def test_reportes_solo_para_administrativos(self):
        for usuario in (self.tutor_user, self.teacher):
            cliente = APIClient()
            cliente.force_authenticate(usuario)
            self.assertEqual(cliente.get(MOROSIDAD).status_code, 403)
            self.assertEqual(cliente.get(SIMULACION, {'desde': '2026-01-01', 'hasta': '2026-02-01'}).status_code, 403)

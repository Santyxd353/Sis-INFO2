from decimal import Decimal
from unittest.mock import patch
from django.utils import timezone
from aplicaciones.calendario.models import Periodo
from aplicaciones.personal.models import Profesor
from rest_framework.test import APITestCase
from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import EventoAuditoria, PermisoPuesto, Usuario
from .models import CorreccionCalificacion, ResultadoTrimestral, ResultadoAnual, ActividadEvaluacion


class CorreccionesTests(SchoolFixture, APITestCase):
    url = '/api/academico/correcciones/'

    def setUp(self):
        self.client.force_authenticate(self.teacher)

    def request_correction(self, **changes):
        payload = {'calificacion': self.grade.pk, 'valor_nuevo': '80.00', 'motivo': 'Revisión del examen'}
        payload.update(changes)
        return self.client.post(self.url, payload, format='json')

    def request_id(self):
        r = self.request_correction()
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def test_request_identity_and_duplicate(self):
        r = self.request_correction(valor_anterior='0', solicitado_por=self.director.pk)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['valor_anterior'], '60.00')
        self.assertEqual(r.data['solicitado_por'], self.teacher.pk)
        self.assertEqual(self.request_correction().status_code, 409)

    def test_approve_recalculates_preserves_evidence(self):
        pk = self.request_id()
        self.client.force_authenticate(self.director)
        r = self.client.post(f'{self.url}{pk}/aprobar/')
        self.assertEqual(r.status_code, 200, r.data)
        self.grade.refresh_from_db()
        self.assertEqual(self.grade.valor, Decimal('80'))
        self.assertEqual(ResultadoTrimestral.objects.get().resultado, Decimal('80'))
        self.assertEqual(ResultadoAnual.objects.get().resultado, Decimal('80'))
        row = CorreccionCalificacion.objects.get(pk=pk)
        self.assertEqual(row.valor_anterior, Decimal('60'))
        self.assertEqual(row.autorizado_por_id, self.director.pk)
        self.assertIsNotNone(row.resuelto_at)
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 409)

    def test_rejection_does_not_change_grade(self):
        pk = self.request_id()
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(f'{self.url}{pk}/rechazar/').status_code, 200)
        self.grade.refresh_from_db()
        self.assertEqual(self.grade.valor, Decimal('60'))
        self.assertFalse(ResultadoTrimestral.objects.exists())

    def test_invalid_request(self):
        for data in ({'motivo': '  '}, {'valor_nuevo': '-1'}, {'valor_nuevo': '101'}, {'valor_nuevo': '60'}):
            self.assertEqual(self.request_correction(**data).status_code, 400)
        self.period.estado = 'CUR'; self.period.save()
        self.assertEqual(self.request_correction().status_code, 400)

    def test_teacher_scope_and_no_edit_bypass(self):
        pk = self.request_id()
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 403)
        self.assertEqual(self.client.patch(f'{self.url}{pk}/', {'valor_nuevo': 90}).status_code, 405)
        self.client.force_authenticate(self.other_teacher)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.assertEqual(self.request_correction().status_code, 400)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(f'{self.url}{pk}/').status_code, 404)

    def test_missing_grade_rolls_back(self):
        pk = self.request_id()
        ActividadEvaluacion.objects.create(asignacion_docente=self.assignment, periodo=self.period, dimension=self.dimension, nombre='Sin nota', fecha='2026-03-02', puntaje_maximo=100)
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 400)
        self.grade.refresh_from_db()
        self.assertEqual(self.grade.valor, Decimal('60'))
        self.assertEqual(CorreccionCalificacion.objects.get(pk=pk).estado, 'SOLICITADA')

    def test_stale_value_and_revoked_permissions(self):
        pk = self.request_id()
        self.grade.valor = 65; self.grade.save()
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 409)
        PermisoPuesto.objects.filter(puesto=self.director.admin.puesto, modelo__nombre='correccion-nota').delete()
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 403)

    def test_calificable_catalog(self):
        r = self.client.get('/api/academico/calificaciones-corregibles/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['results'][0]['id'], self.grade.pk)
        self.client.force_authenticate(self.other_teacher)
        self.assertEqual(self.client.get('/api/academico/calificaciones-corregibles/').data['count'], 0)

    def test_audit_failure_rolls_back_approval(self):
        pk = self.request_id()
        self.client.force_authenticate(self.director)
        with patch('aplicaciones.academico.correcciones_services.registrar_evento', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(f'{self.url}{pk}/aprobar/')
        self.grade.refresh_from_db()
        self.assertEqual(self.grade.valor, Decimal('60'))
        self.assertEqual(CorreccionCalificacion.objects.get(pk=pk).estado, 'SOLICITADA')
        self.assertFalse(ResultadoTrimestral.objects.exists())

    def test_closed_results_stay_closed(self):
        ResultadoTrimestral.objects.create(historial_inscripcion=self.enrollment, materia=self.subject, periodo=self.period, resultado=60, condicion='APROBADO', calculado_at=timezone.now(), estado='CERRADO')
        ResultadoAnual.objects.create(historial_inscripcion=self.enrollment, materia=self.subject, resultado=60, condicion='APROBADO', calculado_at=timezone.now(), estado='CERRADO')
        pk = self.request_id()
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 200)
        self.assertEqual(ResultadoTrimestral.objects.get().estado, 'CERRADO')
        self.assertEqual(ResultadoAnual.objects.get().estado, 'CERRADO')
        self.period.refresh_from_db()
        self.assertEqual(self.period.estado, 'FIN')

    def test_missing_future_period_does_not_create_partial_annual(self):
        Periodo.objects.create(calendario=self.calendar, tipo_division='TRI', nombre='T2', fecha_inicio='2026-05-01', fecha_fin='2026-08-01', estado='PLA')
        pk = self.request_id()
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 200)
        self.assertFalse(ResultadoAnual.objects.exists())

    def test_incomplete_existing_annual_rejects_and_rolls_back(self):
        Periodo.objects.create(calendario=self.calendar, tipo_division='TRI', nombre='T2', fecha_inicio='2026-05-01', fecha_fin='2026-08-01', estado='FIN')
        ResultadoAnual.objects.create(historial_inscripcion=self.enrollment, materia=self.subject, resultado=60, condicion='APROBADO', calculado_at=timezone.now())
        pk = self.request_id()
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 400)
        self.grade.refresh_from_db()
        self.assertEqual(self.grade.valor, Decimal('60'))
        self.assertEqual(ResultadoAnual.objects.get().resultado, Decimal('60'))

    def test_precision_rejection_is_atomic(self):
        pk = self.request_id()
        self.config.decimales = 3
        self.config.save()
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 400)
        self.grade.refresh_from_db()
        self.assertEqual(self.grade.valor, Decimal('60'))

    def test_cannot_resolve_own_request_even_as_director(self):
        pk = self.request_id()
        CorreccionCalificacion.objects.filter(pk=pk).update(solicitado_por=self.director)
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 403)

    def test_teacher_without_profile_cannot_read_unit_grades(self):
        pk = self.request_id()
        partial = Usuario.objects.create_user(ci='partial-teacher', email='partial@example.com', nombre='Partial', apellido='Teacher', username='partial-teacher', fecha_nacimiento='1990-01-01', rol=self.teacher.rol, unidad=self.unit)
        self.client.force_authenticate(partial)
        self.assertEqual(self.client.get('/api/academico/calificaciones-corregibles/').data['count'], 0)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.assertEqual(self.client.get(f'{self.url}{pk}/').status_code, 404)
        self.assertEqual(self.request_correction().status_code, 400)

    def test_director_with_teacher_profile_can_review_other_teacher(self):
        pk = self.request_id()
        Profesor.objects.create(usuario=self.director, unidad=self.unit)
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.get(self.url).data['count'], 1)
        self.assertEqual(self.client.post(f'{self.url}{pk}/aprobar/').status_code, 200)

from unittest.mock import patch
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import EventoAuditoria
from .models import IncidenteDisciplinario, AccionDisciplinaria, Estudiante, TutorEstudiante
from aplicaciones.usuarios.models import Usuario


class DisciplinaTests(SchoolFixture, APITestCase):
    url = '/api/estudiantes/incidentes/'

    def setUp(self):
        self.client.force_authenticate(self.regent)

    def incident(self):
        return self.client.post(self.url, {'historial_inscripcion': self.enrollment.pk, 'fecha': '2026-03-01T12:00:00Z', 'tipo': 'FALTA', 'severidad': 'LEVE', 'descripcion': 'Observación de prueba'}, format='json')

    def citation(self):
        incident = self.incident()
        self.assertEqual(incident.status_code, 201, incident.data)
        return self.client.post('/api/estudiantes/citaciones/', {'incidente': incident.data['id'], 'tutor_estudiante': self.tutor.pk, 'fecha_programada': '2026-04-01T12:00:00Z', 'descripcion': 'Reunión'}, format='json')

    def test_register_history_and_audit(self):
        response = self.incident()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['created_by'], self.regent.pk)
        self.assertEqual(self.client.get(self.url, {'estudiante': self.student.pk}).data['count'], 1)
        self.assertTrue(EventoAuditoria.objects.filter(entidad='INCIDENTE_DISCIPLINARIO').exists())
        self.assertEqual(self.client.delete(f"{self.url}{response.data['id']}/").status_code, 405)

    def test_update_audited_and_identity_immutable(self):
        response = self.incident()
        self.assertEqual(response.status_code, 201)
        response = self.client.patch(f"{self.url}{response.data['id']}/", {'descripcion': 'Actualizada', 'created_by': self.director.pk}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_by'], self.regent.pk)
        self.assertEqual(EventoAuditoria.objects.filter(entidad='INCIDENTE_DISCIPLINARIO').count(), 2)

    def test_citation_transitions(self):
        r = self.citation()
        self.assertEqual(r.status_code, 201, r.data)
        url = f"/api/estudiantes/citaciones/{r.data['id']}/estado/"
        for state in ('ENTREGADA', 'ATENDIDA'):
            self.assertEqual(self.client.post(url, {'estado': state}).status_code, 200)
        self.assertEqual(self.client.post(url, {'estado': 'PENDIENTE'}).status_code, 400)
        self.assertEqual(self.client.patch(url.replace('estado/', ''), {'descripcion': 'alterada'}).status_code, 400)

    def test_direct_attended_and_missing_tutor(self):
        r = self.citation()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.post(f"/api/estudiantes/citaciones/{r.data['id']}/estado/", {'estado': 'ATENDIDA'}).status_code, 200)
        self.assertEqual(self.client.post('/api/estudiantes/citaciones/', {'incidente': r.data['incidente'], 'fecha_programada': '2026-05-01T00:00:00Z'}).status_code, 400)

    def test_unauthorized_and_cross_school(self):
        r = self.incident()
        self.assertEqual(r.status_code, 201)
        for u in (self.teacher, self.tutor_user, self.student_user):
            self.client.force_authenticate(u)
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.assertEqual(self.client.get(f"{self.url}{r.data['id']}/").status_code, 404)
        self.assertEqual(self.incident().status_code, 400)

    def test_catalogs_scoped(self):
        r = self.client.get('/api/estudiantes/inscripciones-disciplina/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['results'][0]['id'], self.enrollment.pk)
        self.client.force_authenticate(self.outsider)
        r = self.client.get('/api/estudiantes/tutores-disciplina/', {'historial_inscripcion': self.enrollment.pk})
        self.assertIn(r.status_code, (400, 404))

    def test_required_fields_and_bad_filters(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        for query in ({'estudiante': '-1'}, {'desde': 'invalid'}, {'desde': '2026-05-01', 'hasta': '2026-01-01'}):
            self.assertEqual(self.client.get(self.url, query).status_code, 400)

    def test_jwt_and_anonymous(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.regent)}')
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_audit_failure_rolls_back_incident(self):
        with patch('aplicaciones.estudiantes.disciplina_api.registrar_evento', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.incident()
        self.assertEqual(IncidenteDisciplinario.objects.count(), 0)

    def test_citation_rejects_other_student_tutor_link(self):
        u = Usuario.objects.create_user(ci='other-child', email='other-child@example.com', nombre='Otro', apellido='Alumno', username='other-child', fecha_nacimiento='2015-01-01', unidad=self.unit, rol=self.student_user.rol)
        other = Estudiante.objects.create(usuario=u, rude='OTHER-RUDE', curso=self.course, unidad=self.unit)
        link = TutorEstudiante.objects.create(estudiante=other, tutor=self.tutor.tutor)
        incident = self.incident()
        self.assertEqual(self.client.post('/api/estudiantes/citaciones/', {'incidente': incident.data['id'], 'tutor_estudiante':link.pk, 'fecha_programada':'2026-05-01T12:00:00Z'}).status_code, 400)
        self.assertFalse(AccionDisciplinaria.objects.exists())

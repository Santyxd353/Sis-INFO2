from datetime import date
from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from aplicaciones.institucion.models import Aula, Modulo
from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import Accion, ModeloPermitido, PermisoPuesto, PermisoRol, EventoAuditoria
from .models import AsignacionDocente, BloqueHorario, Curso, HorarioClase, Materia, MateriaCurso, Paralelo


class HorarioFixture(SchoolFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.calendar.activo = True
        cls.calendar.save()
        model, _ = ModeloPermitido.objects.get_or_create(nombre='horario')
        for name in ('listar', 'crear', 'editar', 'eliminar'):
            action, _ = Accion.objects.get_or_create(nombre=name)
            PermisoPuesto.objects.get_or_create(puesto=cls.director.admin.puesto, modelo=model, accion=action)
            if name == 'listar':
                PermisoRol.objects.get_or_create(rol=cls.teacher.rol, modelo=model, accion=action)
        module = Modulo.objects.create(
            nombre='A', cantidad_aulas=3, colegio_fk=cls.school,
            unidad_educativa=cls.unit,
        )
        cls.room = Aula.objects.create(modulo=module, nombre='A1', capacidad=30)
        cls.room2 = Aula.objects.create(modulo=module, nombre='A2', capacidad=30)
        other_module = Modulo.objects.create(
            nombre='B', cantidad_aulas=1, colegio_fk=cls.other_unit.colegio,
            unidad_educativa=cls.other_unit,
        )
        cls.foreign_room = Aula.objects.create(modulo=other_module, nombre='B1', capacidad=30)
        cls.course2 = Curso.objects.create(paralelo=Paralelo.objects.create(grado=cls.course.paralelo.grado, letra='B'), nombre='Tercero B')
        mc = MateriaCurso.objects.create(curso=cls.course2, materia=cls.subject)
        cls.assignment2 = AsignacionDocente.objects.create(tipo='MATERIA', curso=cls.course2, materia_curso=mc, profesor=cls.prof, calendario_academico=cls.calendar, fecha_inicio=date(2026, 1, 1))
        mc2 = MateriaCurso.objects.create(curso=cls.course, materia=Materia.objects.create(nombre='Lenguaje'))
        cls.assignment3 = AsignacionDocente.objects.create(tipo='MATERIA', curso=cls.course, materia_curso=mc2, profesor=cls.other_teacher.profesor, calendario_academico=cls.calendar, fecha_inicio=date(2026, 1, 1))

    def payload(self, **overrides):
        return dict(asignacion_docente=self.assignment.pk, aula=self.room.pk, dia=1,
                    hora_inicio='08:00', hora_fin='09:00', fecha_inicio='2026-01-01',
                    fecha_fin='2026-12-31') | overrides


class HorarioTests(HorarioFixture, APITestCase):
    url = '/api/academico/horarios/'

    def setUp(self):
        self.client.force_authenticate(self.director)

    def create(self, **kwargs):
        return self.client.post(self.url, self.payload(**kwargs), format='json')

    def saved(self, **kwargs):
        response = self.create(**kwargs)
        self.assertEqual(response.status_code, 201, getattr(response, 'data', 'missing endpoint'))
        return response.data

    def test_create_derives_identity_and_audits(self):
        row = self.saved(profesor=self.other_teacher.pk, curso=self.course2.pk)
        self.assertEqual(row['profesor'], self.prof.pk)
        self.assertEqual(row['curso'], self.course.pk)
        self.assertEqual(row['materia_nombre'], 'Matemática')
        self.assertEqual(row['hora_inicio'], '08:00:00')
        self.assertEqual(EventoAuditoria.objects.filter(entidad='HORARIO_CLASE', accion='CREAR').count(), 1)

    def test_teacher_overlap_across_courses(self):
        self.saved()
        response = self.create(asignacion_docente=self.assignment2.pk, aula=self.room2.pk, hora_inicio='08:30', hora_fin='09:30')
        self.assertEqual(response.status_code, 409)
        self.assertIn('docente', str(response.data).lower())
        self.assertEqual(HorarioClase.objects.count(), 1)

    def test_course_overlap_with_different_teacher(self):
        self.saved()
        response = self.create(asignacion_docente=self.assignment3.pk, aula=self.room2.pk)
        self.assertEqual(response.status_code, 409)
        self.assertIn('curso', str(response.data).lower())

    def test_room_overlap(self):
        self.saved()
        self.assignment2.profesor = self.other_teacher.profesor
        self.assignment2.save()
        response = self.create(asignacion_docente=self.assignment2.pk)
        self.assertEqual(response.status_code, 409)
        self.assertIn('aula', str(response.data).lower())

    def test_adjacent_hours_other_days_and_non_overlapping_dates_allowed(self):
        self.saved(fecha_fin='2026-06-30')
        self.saved(hora_inicio='09:00', hora_fin='10:00')
        self.saved(dia=2)
        self.saved(fecha_inicio='2026-07-01')
        self.assertEqual(HorarioClase.objects.count(), 4)

    def test_overlap_only_when_shared_weekday_occurs(self):
        self.saved(fecha_inicio='2026-01-05', fecha_fin='2026-01-08')
        self.saved(fecha_inicio='2026-01-07', fecha_fin='2026-01-12')
        self.assertEqual(HorarioClase.objects.count(), 2)

    def test_invalid_times_dates_day_and_inactive_assignment(self):
        for changes in ({'hora_fin': '08:00'}, {'hora_fin': '07:00'}, {'dia': 0}, {'dia': 8},
                        {'fecha_fin': '2025-12-31'}, {'fecha_inicio': '2025-12-31'},
                        {'fecha_fin': '2027-01-01'}, {'fecha_fin': None},
                        {'fecha_inicio': '2026-01-06', 'fecha_fin': '2026-01-07'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.create(**changes).status_code, 400)
        self.assignment.estado = 'INACTIVO'
        self.assignment.save()
        self.assertEqual(self.create().status_code, 400)
        self.assertEqual(HorarioClase.objects.count(), 0)

    def test_rejects_foreign_and_unowned_room(self):
        self.assertEqual(self.create(aula=self.foreign_room.pk).status_code, 400)
        orphan = Aula.objects.create(nombre='Sin colegio', capacidad=20)
        self.assertEqual(self.create(aula=orphan.pk).status_code, 400)

    def test_update_is_self_excluding_and_checks_conflicts(self):
        row = self.saved()
        endpoint = f"{self.url}{row['id']}/"
        self.assertEqual(self.client.patch(endpoint, {'hora_fin': '09:15'}).status_code, 200)
        self.saved(hora_inicio='10:00', hora_fin='11:00')
        self.assertEqual(self.client.patch(endpoint, {'hora_fin': '10:30'}).status_code, 409)
        self.assertEqual(str(HorarioClase.objects.get(pk=row['id']).bloque_horario.hora_fin), '09:15:00')

    def test_delete_and_protected_delete(self):
        row = self.saved()
        self.assertEqual(self.client.delete(f"{self.url}{row['id']}/").status_code, 204)
        self.assertFalse(HorarioClase.objects.exists())
        self.assertTrue(EventoAuditoria.objects.filter(entidad='HORARIO_CLASE', accion='ELIMINAR').exists())
        from aplicaciones.estudiantes.models import SesionClase
        row = self.saved()
        SesionClase.objects.create(asignacion_docente=self.assignment, horario_clase_id=row['id'], fecha='2026-03-02', profesor_efectivo=self.prof, aula_efectiva=self.room)
        self.assertEqual(self.client.delete(f"{self.url}{row['id']}/").status_code, 409)
        self.assertEqual(self.client.patch(f"{self.url}{row['id']}/", {'dia': 3}).status_code, 409)

    def test_weekly_filters_and_validation(self):
        self.saved(fecha_inicio='2026-01-06')  # Tuesday, first occurrence Monday 12.
        self.assertEqual(self.client.get(self.url, {'semana': '2026-01-07'}).data['count'], 0)
        self.assertEqual(self.client.get(self.url, {'semana': '2026-01-14', 'curso': self.course.pk}).data['count'], 1)
        self.assertEqual(self.client.get(self.url, {'profesor': self.other_teacher.pk}).data['count'], 0)
        for params in ({'semana': 'oops'}, {'curso': 'x'}, {'gestion': '-1'}):
            self.assertEqual(self.client.get(self.url, params).status_code, 400)

    def test_personal_scope_and_revoked_permission(self):
        self.saved()
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(self.url).data['count'], 1)
        self.assertEqual(self.create().status_code, 403)
        self.client.force_authenticate(self.other_teacher)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.assignment3.delete()
        self.other_teacher.profesor.delete()
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.client.force_authenticate(self.director)
        PermisoPuesto.objects.filter(puesto=self.director.admin.puesto, modelo__nombre='horario', accion__nombre='eliminar').delete()
        row = HorarioClase.objects.get()
        self.assertEqual(self.client.delete(f'{self.url}{row.pk}/').status_code, 403)

    def test_jwt_required_and_supported(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.director)}')
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_foreign_detail_and_mutations_are_hidden(self):
        row = self.saved()
        self.client.force_authenticate(self.outsider)
        endpoint = f"{self.url}{row['id']}/"
        self.assertEqual(self.client.get(endpoint).status_code, 404)
        self.assertEqual(self.client.patch(endpoint, {'dia': 3}).status_code, 404)
        self.assertEqual(self.client.delete(endpoint).status_code, 404)
        self.assertEqual(self.create().status_code, 400)

    def test_legacy_open_ended_schedule_requires_explicit_end_for_edit(self):
        row = self.saved()
        HorarioClase.objects.filter(pk=row['id']).update(fecha_fin=None)
        endpoint = f"{self.url}{row['id']}/"
        self.assertEqual(self.client.patch(endpoint, {'hora_fin': '09:15'}).status_code, 400)
        self.assertEqual(self.client.patch(endpoint, {'fecha_fin': '2026-12-31', 'hora_fin': '09:15'}).status_code, 200)

    def test_catalogs_scope_search_and_pagination(self):
        for catalog in ('asignaciones', 'aulas', 'cursos', 'profesores'):
            url = f'/api/academico/horarios-{catalog}/'
            result = self.client.get(url, {'page_size': 1})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(len(result.data['results']), 1)
            self.assertTrue(result.data['next'])
            self.assertEqual(self.client.get(url, {'search': 'nothingmatches'}).data['count'], 0)
        rooms = self.client.get('/api/academico/horarios-aulas/').data['results']
        self.assertNotIn(self.foreign_room.pk, [r['id'] for r in rooms])
        self.client.force_authenticate(self.teacher)
        rows = self.client.get('/api/academico/horarios-profesores/').data['results']
        self.assertEqual([r['id'] for r in rows], [self.prof.pk])

    def test_room_catalog_derives_unit_from_assignment(self):
        url = '/api/academico/horarios-aulas/'
        response = self.client.get(url, {'asignacion_docente': self.assignment.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row['id'] for row in response.data['results']}, {self.room.pk, self.room2.pk})
        self.assertEqual(
            self.client.get(url, {
                'asignacion_docente': self.assignment.pk,
                'unidad_educativa': self.other_unit.pk,
            }).status_code,
            400,
        )
        self.assertEqual(self.client.get(url, {'asignacion_docente': 999999}).data['count'], 0)

    def test_audit_failure_rolls_back_schedule_and_block(self):
        with patch('aplicaciones.academico.horarios_api.registrar_evento', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertFalse(HorarioClase.objects.exists())
        self.assertFalse(BloqueHorario.objects.exists())

    def test_read_filters_keep_historical_courses_and_teachers(self):
        self.saved()
        self.calendar.activo = False
        self.calendar.save()
        self.assertEqual(self.client.get(self.url, {'semana': '2026-10-12'}).data['count'], 1)
        for catalog, pk in (('cursos', self.course.pk), ('profesores', self.prof.pk)):
            result = self.client.get(f'/api/academico/horarios-{catalog}/')
            self.assertIn(pk, [row['id'] for row in result.data['results']])
        self.assertEqual(self.client.get('/api/academico/horarios-asignaciones/').data['count'], 0)

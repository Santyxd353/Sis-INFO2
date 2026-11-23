from rest_framework.test import APITestCase
from django.utils import timezone
from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import PermisoPuesto, Usuario, Rol
from aplicaciones.estudiantes.models import Estudiante, TutorEstudiante, HistorialInscripcion, AsistenciaEstudiante, SesionClase
from aplicaciones.academico.models import ResultadoTrimestral, ResultadoAnual, Grado, Paralelo, Curso, MateriaCurso, AsignacionDocente, BloqueHorario, HorarioClase
from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from aplicaciones.comunicacion.models import Comunicado, DestinatarioComunicado, Aviso
from aplicaciones.asistencia.models import RegistroAsistencia, DetalleAsistencia
from aplicaciones.institucion.models import Aula, Modulo, UnidadEducativa
from aplicaciones.estudiantes.models import DocumentoAcademicoEmitido
from aplicaciones.usuarios.models import Accion, ModeloPermitido, PermisoRol


class PortalRouteTests(APITestCase):
    def test_portal_requires_jwt_and_disables_caching_even_on_errors(self):
        for url in ('/api/portal/familia/', '/api/portal/panel-director/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response['Cache-Control'], 'no-store')


class PortalTests(SchoolFixture, APITestCase):
    family = '/api/portal/familia/'
    panel = '/api/portal/panel-director/'

    def setUp(self):
        self.client.force_authenticate(self.tutor_user)

    def get(self, url=None, **params):
        response = self.client.get(url or self.family, params)
        self.assertEqual(response['Cache-Control'], 'no-store')
        return response

    def result(self, value=80, **extra):
        return ResultadoTrimestral.objects.create(historial_inscripcion=self.enrollment,
            materia=self.subject, periodo=self.period, resultado=value, condicion='APROBADO',
            calculado_at=timezone.now(), **extra)

    def legacy(self, state='P', date='2026-03-01'):
        register = RegistroAsistencia.objects.create(asignacion=self.assignment.materia_curso,
            fecha=date, periodo=self.period, docente=self.teacher)
        return DetalleAsistencia.objects.create(registro=register, estudiante=self.student, estado=state)

    def test_family_contract_empty_academics_and_honest_unavailable_payments(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data['seleccionado'], self.student.pk)
        self.assertEqual(data['estudiante']['curso'], self.course.nombre)
        self.assertEqual(data['gestion']['id'], self.calendar.pk)
        self.assertEqual(data['asistencia']['fuente'], 'SIN_DATOS')
        self.assertIsNone(data['asistencia']['porcentaje'])
        self.assertEqual(data['notas'], [])
        self.assertFalse(data['pagos']['disponible'])
        self.assertTrue(data['pagos']['mensaje'])
        for key in ('gestiones', 'periodos', 'horarios', 'boletines', 'comunicados', 'notificaciones', 'actualizado_at'):
            self.assertIn(key, data)

    def test_tutor_with_no_children_has_empty_payload(self):
        message = Comunicado.objects.create(titulo='Previous', cuerpo='Private', unidad_educativa=self.unit,
            estado='PUBLICADO', publicado_at=timezone.now())
        DestinatarioComunicado.objects.create(comunicado=message, usuario=self.tutor_user)
        TutorEstudiante.objects.all().delete()
        data = self.get().data
        self.assertEqual(data['estudiantes'], [])
        self.assertIsNone(data['seleccionado'])
        self.assertIsNone(data['gestion'])
        self.assertEqual(data['comunicados'], [])

    def test_student_self_only_and_multiple_children_selection(self):
        child_user = Usuario.objects.create_user(ci='second', username='second', email='second@example.com',
            nombre='Ana', apellido='Otro', fecha_nacimiento='2010-01-01', rol=self.student_user.rol, unidad=self.unit)
        child = Estudiante.objects.create(usuario=child_user, rude='second', unidad=self.unit, curso=self.course)
        TutorEstudiante.objects.create(tutor=self.tutor.tutor, estudiante=child)
        self.assertEqual(self.get().data['seleccionado'], child.pk)
        self.assertEqual(self.get(estudiante=self.student.pk).data['seleccionado'], self.student.pk)
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.get().data['seleccionado'], self.student.pk)
        self.assertEqual(self.get(estudiante=child.pk).status_code, 404)

    def test_inactive_roles_profiles_and_cross_tenant_links_are_rejected(self):
        for actor in (self.director, self.teacher, self.regent):
            self.client.force_authenticate(actor)
            self.assertEqual(self.get().status_code, 403)
        self.client.force_authenticate(self.tutor_user)
        self.student.unidad = self.other_unit
        self.student.save(update_fields=['unidad'])
        self.assertEqual(self.get(estudiante=self.student.pk).status_code, 404)
        self.tutor_user.estado = False
        self.assertEqual(self.get().status_code, 403)

    def test_queries_validate_positive_ids_and_period_calendar_scope(self):
        for key in ('estudiante', 'periodo', 'calendario_academico'):
            for value in ('0', '-1', 'x', ''):
                self.assertEqual(self.get(**{key: value}).status_code, 400)
        other = CalendarioAcademico.objects.create(unidad_educativa=self.other_unit, año=2026,
            fecha_inicio='2026-01-01', fecha_fin='2026-12-31')
        period = Periodo.objects.create(calendario=other, nombre='Other', tipo_division='TRI',
            fecha_inicio='2026-01-01', fecha_fin='2026-04-30')
        self.assertEqual(self.get(calendario_academico=other.pk).status_code, 404)
        self.assertEqual(self.get(periodo=period.pk).status_code, 404)

    def test_notes_and_attendance_respect_selected_period_and_do_not_add_legacy_to_sessions(self):
        result = self.result()
        self.legacy('A')
        module = Modulo.objects.create(unidad_educativa=self.unit, nombre='M', cantidad_aulas=1)
        room = Aula.objects.create(modulo=module, nombre='A', capacidad=30)
        session = SesionClase.objects.create(asignacion_docente=self.assignment, fecha='2026-03-01',
            profesor_efectivo=self.prof, aula_efectiva=room)
        AsistenciaEstudiante.objects.create(sesion_clase=session, historial_inscripcion=self.enrollment,
            estado_asistencia='PRESENTE')
        data = self.get(periodo=self.period.pk).data
        self.assertEqual(data['notas'][0]['periodos'][0]['nota'], '80.00')
        self.assertEqual(data['asistencia']['fuente'], 'SESIONES')
        self.assertEqual(data['asistencia']['total'], 1)
        self.assertEqual(data['asistencia']['porcentaje'], 100.0)
        self.assertEqual(data['asistencia']['faltas'], 0)
        second = Periodo.objects.create(calendario=self.calendar, nombre='T2', tipo_division='TRI',
            fecha_inicio='2026-05-01', fecha_fin='2026-08-31')
        data = self.get(periodo=second.pk).data
        self.assertEqual(data['notas'], [])
        self.assertEqual(data['asistencia']['total'], 0)

    def test_legacy_statistics_use_all_rows_but_return_only_latest_50(self):
        from datetime import date, timedelta
        for offset in range(55):
            self.legacy('P', date(2026, 2, 1) + timedelta(days=offset))
        attendance = self.get().data['asistencia']
        self.assertEqual(attendance['fuente'], 'LEGACY')
        self.assertEqual(attendance['total'], 55)
        self.assertEqual(len(attendance['registros']), 50)

    def test_historical_calendar_uses_its_enrollment_and_never_ambiguous_annual(self):
        old = CalendarioAcademico.objects.create(unidad_educativa=self.unit, año=2025,
            fecha_inicio='2025-01-01', fecha_fin='2025-12-31')
        old_period = Periodo.objects.create(calendario=old, nombre='Old', tipo_division='TRI',
            fecha_inicio='2025-01-01', fecha_fin='2025-04-30')
        self.result()
        ResultadoTrimestral.objects.create(historial_inscripcion=self.enrollment, materia=self.subject,
            periodo=old_period, resultado=40, condicion='REPROBADO', calculado_at=timezone.now())
        ResultadoAnual.objects.create(historial_inscripcion=self.enrollment, materia=self.subject,
            resultado=60, condicion='APROBADO', calculado_at=timezone.now())
        data = self.get(calendario_academico=old.pk).data
        self.assertEqual(data['notas'][0]['periodos'][0]['nota'], '40.00')
        self.assertIsNone(data['notas'][0]['anual'])

    def test_communication_uses_own_snapshot_and_inbox_only(self):
        message = Comunicado.objects.create(titulo='Aviso', cuerpo='Private', unidad_educativa=self.unit,
            creado_por=self.director, estado='PUBLICADO', publicado_at=timezone.now())
        DestinatarioComunicado.objects.create(comunicado=message, usuario=self.tutor_user)
        Aviso.objects.create(usuario=self.tutor_user, unidad_educativa=self.unit, tipo='COMUNICADO',
            titulo='Aviso', cuerpo='Private', clave_evento='own', comunicado=message)
        Aviso.objects.create(usuario=self.student_user, unidad_educativa=self.unit, tipo='PAGO',
            titulo='Other', cuerpo='Private', clave_evento='other')
        data = self.get().data
        self.assertEqual([row['id'] for row in data['comunicados']], [message.pk])
        self.assertEqual(data['notificaciones']['no_leidas'], 1)
        self.assertEqual(len(data['notificaciones']['recientes']), 1)
        self.assertNotIn('cuerpo', data['comunicados'][0])

    def test_director_requires_specific_permission_and_school_scope(self):
        for actor in (self.tutor_user, self.student_user, self.regent, self.teacher):
            self.client.force_authenticate(actor)
            self.assertEqual(self.get(self.panel).status_code, 403)
        self.client.force_authenticate(self.director)
        response = self.get(self.panel)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['alcance']['colegio_id'], self.school.pk)
        self.assertEqual(self.get(self.panel, unidad_educativa=self.other_unit.pk).status_code, 404)
        PermisoPuesto.objects.filter(puesto=self.director.admin.puesto, modelo__nombre='portal-panel').delete()
        self.assertEqual(self.get(self.panel).status_code, 403)

    def test_panel_counts_current_and_filters_academic_and_read_metrics(self):
        self.result()
        self.legacy('P')
        self.client.force_authenticate(self.director)
        all_data = self.get(self.panel).data
        self.assertIsNone(all_data['indicadores']['promedio'])
        data = self.get(self.panel, unidad_educativa=self.unit.pk, periodo=self.period.pk).data
        metrics = data['indicadores']
        self.assertEqual(metrics['estudiantes_activos'], 1)
        self.assertEqual(metrics['docentes_activos'], 2)
        self.assertEqual(metrics['cursos'], 1)
        self.assertEqual(metrics['promedio'], 80.0)
        self.assertEqual(metrics['porcentaje_aprobacion'], 100.0)
        self.assertEqual(metrics['porcentaje_asistencia'], 100.0)
        self.assertIsNone(metrics['porcentaje_lectura'])

    def test_all_errors_and_unsupported_methods_remain_no_store(self):
        for method in ('post', 'patch', 'delete'):
            response = getattr(self.client, method)(self.family)
            self.assertEqual(response.status_code, 405)
            self.assertEqual(response['Cache-Control'], 'no-store')
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        self.assertEqual(self.get().status_code, 401)

    def second_unit_child(self):
        unit = UnidadEducativa.objects.create(colegio=self.school, codigo_sie='same-school', nombre='Unidad C', turno='TARDE')
        grade = Grado.objects.create(unidad_educativa=unit, nivel_educativo='PRI', numero=3)
        course = Curso.objects.create(paralelo=Paralelo.objects.create(grado=grade, letra='A'), nombre='Otro curso')
        user = Usuario.objects.create_user(ci='child2', username='child2', email='child2@example.com',
            nombre='Ana', apellido='Dos', fecha_nacimiento='2010-01-01', rol=self.student_user.rol, unidad=unit)
        student = Estudiante.objects.create(usuario=user, rude='child2', unidad=unit, curso=course)
        TutorEstudiante.objects.create(tutor=self.tutor.tutor, estudiante=student)
        enrollment = HistorialInscripcion.objects.create(estudiante=student, unidad=unit, curso_nuevo=course)
        calendar = CalendarioAcademico.objects.create(unidad_educativa=unit, año=2026, fecha_inicio='2026-01-01', fecha_fin='2026-12-31')
        return unit, student, enrollment, calendar

    def document(self, enrollment=None, calendar=None):
        return DocumentoAcademicoEmitido.objects.create(tipo='BOLETIN', historial_inscripcion=enrollment or self.enrollment,
            calendario_academico=calendar or self.calendar, version=1, archivo_ref='hu29-test.pdf',
            archivo_mime='application/pdf', archivo_tamano=10, archivo_checksum='abc', emitido_at=timezone.now())

    def test_tutor_may_select_linked_children_in_another_unit_of_same_school(self):
        unit, student, enrollment, calendar = self.second_unit_child()
        data = self.get(estudiante=student.pk).data
        self.assertEqual(data['estudiante']['unidad_educativa'], unit.pk)
        self.assertEqual(data['gestion']['id'], calendar.pk)
        self.assertEqual(len(data['estudiantes']), 2)
        unit.colegio = self.other_unit.colegio
        unit.save(update_fields=['colegio'])
        self.assertEqual(self.get(estudiante=student.pk).status_code, 404)

    def test_existing_document_download_allows_linked_child_same_school_and_blocks_tampered_tenant(self):
        import tempfile
        from django.test import override_settings
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        unit, student, enrollment, calendar = self.second_unit_child()
        doc = self.document(enrollment, calendar)
        model, _ = ModeloPermitido.objects.get_or_create(nombre='documento-academico')
        action, _ = Accion.objects.get_or_create(nombre='descargar')
        PermisoRol.objects.get_or_create(rol=self.tutor_user.rol, modelo=model, accion=action)
        url = f'/api/estudiantes/documentos-academicos/{doc.pk}/descargar/'
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            default_storage.save('hu29-test.pdf', ContentFile(b'%PDF-private'))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'%PDF-private')
            enrollment.unidad = self.other_unit
            enrollment.save(update_fields=['unidad'])
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_document_links_are_private_and_limit_to_selected_history_and_calendar(self):
        doc = self.document()
        data = self.get().data
        self.assertEqual(data['boletines'][0]['descarga_url'], f'/api/estudiantes/documentos-academicos/{doc.pk}/descargar/')
        self.assertNotIn('archivo_ref', data['boletines'][0])

    def test_panel_aggregates_own_snapshot_reads_and_excludes_foreign_school_messages(self):
        for unit, reads in ((self.unit, [True, False]), (self.other_unit, [True])):
            message = Comunicado.objects.create(titulo='Message', cuerpo='Private', unidad_educativa=unit,
                estado='PUBLICADO', publicado_at='2026-03-01T10:00:00Z')
            for user, read in zip((self.student_user, self.tutor_user), reads):
                DestinatarioComunicado.objects.create(comunicado=message, usuario=user,
                    leido_at=timezone.now() if read else None)
        self.client.force_authenticate(self.director)
        metrics = self.get(self.panel, unidad_educativa=self.unit.pk, periodo=self.period.pk).data['indicadores']
        self.assertEqual(metrics['comunicados_publicados'], 1)
        self.assertEqual(metrics['porcentaje_lectura'], 50.0)

    def test_schedule_filters_inactive_deleted_foreign_calendar_and_expired_assignments(self):
        from datetime import timedelta
        today = timezone.localdate()
        self.calendar.fecha_inicio = today.replace(month=1, day=1)
        self.calendar.fecha_fin = today.replace(month=12, day=31)
        self.calendar.save()
        self.assignment.fecha_inicio = self.calendar.fecha_inicio
        self.assignment.save()
        module = Modulo.objects.create(unidad_educativa=self.unit, nombre='Schedule', cantidad_aulas=1)
        room = Aula.objects.create(modulo=module, nombre='S', capacidad=30)
        block = BloqueHorario.objects.create(unidad_educativa=self.unit, turno='TARDE', dia=1,
            orden=1, hora_inicio='14:00', hora_fin='15:00')
        schedule = HorarioClase.objects.create(asignacion_docente=self.assignment, profesor=self.prof,
            curso=self.course, aula=room, bloque_horario=block, fecha_inicio=self.calendar.fecha_inicio)
        self.assertEqual(self.get().data['horarios'][0]['id'], schedule.pk)
        foreign_module = Modulo.objects.create(unidad_educativa=self.other_unit, colegio_fk=self.other_unit.colegio,
            nombre='Foreign module', cantidad_aulas=1)
        room.modulo = foreign_module
        room.save()
        self.assertEqual(self.get().data['horarios'], [])
        room.modulo = module
        room.save()
        self.assignment.eliminado_at = timezone.now()
        self.assignment.save()
        self.assertEqual(self.get().data['horarios'], [])
        self.assignment.eliminado_at = None
        self.assignment.fecha_fin = today - timedelta(days=1)
        self.assignment.save()
        self.assertEqual(self.get().data['horarios'], [])

    def test_selected_historical_enrollment_does_not_mix_current_course_notes(self):
        grade = Grado.objects.create(unidad_educativa=self.unit, nivel_educativo='PRI', numero=2)
        course = Curso.objects.create(paralelo=Paralelo.objects.create(grado=grade, letra='A'), nombre='Anterior')
        MateriaCurso.objects.create(curso=course, materia=self.subject)
        previous = HistorialInscripcion.objects.create(estudiante=self.student, unidad=self.unit, curso_nuevo=course)
        self.result()
        old = CalendarioAcademico.objects.create(unidad_educativa=self.unit, año=2025, fecha_inicio='2025-01-01', fecha_fin='2025-12-31')
        period = Periodo.objects.create(calendario=old, nombre='Anterior', tipo_division='TRI', fecha_inicio='2025-01-01', fecha_fin='2025-04-30')
        ResultadoTrimestral.objects.create(historial_inscripcion=previous, materia=self.subject,
            periodo=period, resultado=55, condicion='APROBADO', calculado_at=timezone.now())
        data = self.get(calendario_academico=old.pk).data
        self.assertEqual(data['estudiante']['curso'], 'Anterior')
        self.assertEqual([r['nota'] for r in data['notas'][0]['periodos']], ['55.00'])

    def test_jwt_request_returns_family_and_inactive_director_and_superadmin_are_denied(self):
        from rest_framework_simplejwt.tokens import AccessToken
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.student_user)}')
        self.assertEqual(self.get().status_code, 200)
        self.client.credentials()
        self.director.admin.estado = False
        self.director.admin.save()
        self.client.force_authenticate(self.director)
        self.assertEqual(self.get(self.panel).status_code, 403)

    def test_malformed_foreign_subject_assignment_and_schedule_never_contribute(self):
        # A legacy write bypassing model.clean must not expose another school's subject.
        from aplicaciones.academico.models import Materia
        self.legacy('P')
        foreign = Materia.objects.create(nombre='Foreign private', unidad_educativa=self.other_unit)
        self.assignment.materia_curso.materia = foreign
        self.assignment.materia_curso.save()
        self.result()
        self.assertEqual(self.get().data['asistencia']['total'], 0)
        self.client.force_authenticate(self.director)
        metrics = self.get(self.panel, unidad_educativa=self.unit.pk).data['indicadores']
        self.assertIsNone(metrics['porcentaje_asistencia'])

    def test_malformed_calendar_period_inversion_is_rejected(self):
        second = CalendarioAcademico.objects.create(unidad_educativa=self.unit, año=2025,
            fecha_inicio='2025-01-01', fecha_fin='2025-12-31')
        self.assertEqual(self.get(calendario_academico=second.pk, periodo=self.period.pk).status_code, 404)

    def test_panel_never_counts_incoherent_tenant_grade_or_attendance_rows(self):
        self.result()
        self.legacy()
        self.enrollment.unidad = self.other_unit
        self.enrollment.save()
        self.student_user.unidad = self.other_unit
        self.student_user.save()
        self.client.force_authenticate(self.director)
        metrics = self.get(self.panel, unidad_educativa=self.unit.pk).data['indicadores']
        self.assertEqual(metrics['estudiantes_activos'], 0)
        self.assertIsNone(metrics['promedio'])
        self.assertIsNone(metrics['porcentaje_asistencia'])
        role, _ = Rol.objects.get_or_create(nombre='Superadmin')
        self.tutor_user.rol = role
        self.client.force_authenticate(self.tutor_user)
        self.assertEqual(self.get().status_code, 403)
        self.assertEqual(self.get(self.panel).status_code, 403)

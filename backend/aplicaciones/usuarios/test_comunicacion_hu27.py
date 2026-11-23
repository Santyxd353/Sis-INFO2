from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import EventoAuditoria


class ComunicacionTests(SchoolFixture, APITestCase):
    root = '/api/comunicacion/'

    def setUp(self):
        self.client.force_authenticate(self.director)
        self.push = patch('aplicaciones.usuarios.notificaciones.requests.post').start()
        self.addCleanup(patch.stopall)

    def draft(self, **extra):
        response = self.client.post(self.root + 'comunicados/', {
            'titulo': 'Reunión', 'cuerpo': 'Información privada',
            'unidad_educativa': self.unit.pk, 'curso': self.course.pk,
            'prioridad': 'NORMAL', 'requiere_confirmacion': True, **extra,
        }, format='json')
        self.assertEqual(response.status_code, 201, getattr(response, 'data', response.content))
        self.assertEqual(response.data['estado'], 'BORRADOR')
        return response.data['id']

    def publish(self, pk):
        response = self.client.post(f'{self.root}comunicados/{pk}/publicar/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_publish_snapshot_unique_audience_and_read_statistics(self):
        pk = self.draft()
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.client.get(f'{self.root}comunicados/{pk}/').status_code, 404)
        self.client.force_authenticate(self.director)
        data = self.publish(pk)
        self.assertEqual(data['estadisticas']['destinatarios'], 2)
        self.publish(pk)
        from aplicaciones.comunicacion.models import Aviso, DestinatarioComunicado
        self.assertEqual(Aviso.objects.filter(comunicado_id=pk).count(), 2)
        self.assertEqual(DestinatarioComunicado.objects.filter(comunicado_id=pk).count(), 2)
        self.student.curso = None
        self.student.save(update_fields=['curso'])
        self.client.force_authenticate(self.student_user)
        url = f'{self.root}comunicados/{pk}/leer/'
        first = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        self.assertIsNotNone(first.data['leido_at'])
        self.assertEqual(self.client.post(url).data['leido_at'], first.data['leido_at'])
        self.assertIsNone(first.data['estadisticas'])
        self.assertFalse(first.data['puede_gestionar'])
        self.client.force_authenticate(self.director)
        data = self.client.get(f'{self.root}comunicados/{pk}/').data
        self.assertEqual(data['estadisticas'], {'destinatarios': 2, 'leidos': 1, 'porcentaje_lectura': 50.0})
        self.assertEqual(self.client.patch(f'{self.root}comunicados/{pk}/', {'titulo': 'Cambio'}).status_code, 400)
        self.assertEqual(self.client.post(f'{self.root}comunicados/{pk}/archivar/').data['estado'], 'ARCHIVADO')
        self.assertEqual(self.client.post(f'{self.root}comunicados/{pk}/publicar/').status_code, 400)
        self.assertTrue(EventoAuditoria.objects.filter(entidad='COMUNICADO', entidad_id=str(pk)).exists())

    def test_director_permission_and_tenant_fail_closed(self):
        self.assertEqual(self.client.post(self.root + 'comunicados/', {
            'titulo': 'X', 'cuerpo': 'Y', 'unidad_educativa': self.other_unit.pk,
        }, format='json').status_code, 403)
        pk = self.draft()
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(f'{self.root}comunicados/{pk}/').status_code, 404)
        self.client.force_authenticate(self.regent)
        self.assertEqual(self.client.post(f'{self.root}comunicados/{pk}/publicar/').status_code, 404)
        from aplicaciones.usuarios.models import PermisoPuesto
        PermisoPuesto.objects.filter(puesto=self.director.admin.puesto, modelo__nombre='comunicacion').delete()
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(self.root + 'comunicados/', {
            'titulo': 'X', 'cuerpo': 'Y', 'unidad_educativa': self.unit.pk,
        }, format='json').status_code, 403)

    def test_disabled_director_cannot_create_messages(self):
        self.director.estado = False
        self.director.save(update_fields=['estado'])
        response = self.client.post(self.root + 'comunicados/', {
            'titulo': 'X', 'cuerpo': 'Y', 'unidad_educativa': self.unit.pk,
        }, format='json')
        self.assertEqual(response.status_code, 403)

    def test_institutional_director_is_also_recipient_and_can_confirm(self):
        pk = self.draft(curso=None)
        draft = self.client.get(f'{self.root}comunicados/{pk}/').data
        self.assertEqual(draft.get('es_destinatario'), False)
        published = self.publish(pk)
        self.assertTrue(published['puede_gestionar'])
        self.assertEqual(published.get('es_destinatario'), True)
        response = self.client.post(f'{self.root}comunicados/{pk}/leer/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['es_destinatario'])
        self.assertIsNotNone(response.data['leido_at'])
        archived = self.client.post(f'{self.root}comunicados/{pk}/archivar/').data
        self.assertTrue(archived['es_destinatario'])

    def test_course_manager_is_not_recipient_without_snapshot_membership(self):
        pk = self.draft()
        published = self.publish(pk)
        self.assertTrue(published['puede_gestionar'])
        self.assertEqual(published.get('es_destinatario'), False)
        self.assertEqual(self.client.post(f'{self.root}comunicados/{pk}/leer/').status_code, 404)
        self.client.force_authenticate(self.tutor_user)
        self.assertTrue(self.client.get(f'{self.root}comunicados/{pk}/').data['es_destinatario'])

    def test_snapshot_recipient_moved_outside_unit_cannot_be_confirmable(self):
        from types import SimpleNamespace
        from aplicaciones.comunicacion.models import Comunicado
        from aplicaciones.comunicacion.serializers import ComunicadoSerializer
        pk = self.draft()
        self.publish(pk)
        self.student_user.unidad = self.other_unit
        self.student_user.save(update_fields=['unidad'])
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.client.get(f'{self.root}comunicados/{pk}/').status_code, 404)
        # El booleano también falla cerrado si se serializa un snapshot histórico.
        serialized = ComunicadoSerializer(Comunicado.objects.get(pk=pk),
            context={'request': SimpleNamespace(user=self.student_user)}).data
        self.assertEqual(serialized.get('es_destinatario'), False)

    def test_director_moved_between_school_units_cannot_confirm_old_snapshot(self):
        from aplicaciones.institucion.models import UnidadEducativa
        pk = self.draft(curso=None)
        self.publish(pk)
        another_unit = UnidadEducativa.objects.create(colegio=self.school, nombre='Unidad C',
            codigo_sie='HU-C', turno='TARDE')
        self.director.unidad = another_unit
        self.director.save(update_fields=['unidad'])
        profile = self.director.admin
        profile.unidad = another_unit
        profile.save(update_fields=['unidad'])
        self.assertEqual(self.client.post(f'{self.root}comunicados/{pk}/leer/').status_code, 403)

    def test_inbox_read_filters_preferences_and_alert_idempotency(self):
        payload = {'estudiante': self.student.pk, 'tipo': 'PAGO', 'titulo': 'Aviso',
                   'cuerpo': 'Información privada', 'clave_evento': 'mensualidad-1'}
        url = self.root + 'alertas/'
        self.assertEqual(self.client.post(url, payload, format='json').data, {'creadas': 2})
        self.assertEqual(self.client.post(url, payload, format='json').data, {'creadas': 0})
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 403)
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.client.patch(self.root + 'preferencias/', {'PAGO': False}, format='json').data['PAGO'], False)
        self.assertEqual(self.client.patch(self.root + 'preferencias/', {'inventada': True}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.root + 'preferencias/', {'PAGO': 'false'}, format='json').status_code, 400)
        inbox = self.client.get(self.root + 'notificaciones/?no_leidas=true&tipo=PAGO').data
        self.assertEqual(inbox['count'], 1)
        pk = inbox['results'][0]['id']
        read = self.client.post(f'{self.root}notificaciones/{pk}/leer/').data
        self.assertIsNotNone(read['leida_at'])
        self.assertEqual(self.client.post(f'{self.root}notificaciones/{pk}/leer/').data['leida_at'], read['leida_at'])
        self.assertEqual(self.client.get(self.root + 'notificaciones/resumen/').data['no_leidas'], 0)
        self.client.force_authenticate(self.tutor_user)
        self.assertEqual(self.client.get(f'{self.root}notificaciones/{pk}/').status_code, 404)

    def test_publication_push_after_commit_and_rollback(self):
        from aplicaciones.comunicacion.models import Aviso, Comunicado
        from aplicaciones.usuarios.models import DispositivoNotificacion
        DispositivoNotificacion.objects.create(usuario=self.student_user, token='ExponentPushToken[test]', plataforma='ANDROID')
        pk = self.draft()
        with self.captureOnCommitCallbacks(execute=True):
            self.publish(pk)
            self.assertFalse(self.push.called)
        self.assertTrue(self.push.called)
        message = self.push.call_args.kwargs['json'][0]
        self.assertNotIn('Información privada', str(message))
        sent = self.push.call_count
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    second = self.draft()
                    self.publish(second)
                    raise RuntimeError('rollback')
        self.assertEqual(Comunicado.objects.count(), 1)
        self.assertEqual(Aviso.objects.count(), 2)
        self.assertEqual(self.push.call_count, sent)

    def test_alert_preferences_disable_push_only(self):
        from aplicaciones.usuarios.models import DispositivoNotificacion
        DispositivoNotificacion.objects.create(usuario=self.student_user, token='ExponentPushToken[test]', plataforma='ANDROID')
        self.client.force_authenticate(self.student_user)
        self.client.patch(self.root + 'preferencias/', {'PAGO': False}, format='json')
        self.client.force_authenticate(self.director)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.root + 'alertas/', {'estudiante': self.student.pk,
                'tipo': 'PAGO', 'titulo': 'Pago', 'cuerpo': 'Detalle', 'clave_evento': 'p-2'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(self.push.called)
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.client.get(self.root + 'notificaciones/').data['count'], 1)

    def test_attendance_and_low_grade_events_do_not_duplicate_or_cross_tenant(self):
        from aplicaciones.asistencia.models import DetalleAsistencia, RegistroAsistencia
        from aplicaciones.academico.models import ResultadoTrimestral
        from aplicaciones.comunicacion.models import Aviso
        registration = RegistroAsistencia.objects.create(asignacion=self.assignment.materia_curso,
            fecha='2026-03-01', docente=self.teacher)
        detail = DetalleAsistencia.objects.create(registro=registration, estudiante=self.student, estado='A')
        detail.save()
        self.assertEqual(Aviso.objects.filter(tipo='FALTA').count(), 2)
        detail.estado = 'T'
        detail.save()
        self.assertEqual(Aviso.objects.filter(tipo='ATRASO').count(), 2)
        result = ResultadoTrimestral.objects.create(historial_inscripcion=self.enrollment,
            materia=self.subject, periodo=self.period, resultado=40, condicion='REPROBADO', calculado_at=timezone.now())
        result.save()
        self.assertEqual(Aviso.objects.filter(tipo='NOTA_BAJA').count(), 2)
        self.config.nota_aprobacion = 70
        self.config.save()
        result.resultado = 65
        result.save()
        self.assertEqual(Aviso.objects.filter(tipo='NOTA_BAJA').count(), 2)
        self.student_user.unidad = self.other_unit
        self.student_user.save(update_fields=['unidad'])
        detail.estado = 'P'
        detail.save()
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.client.get(self.root + 'notificaciones/').data['count'], 0)

    def test_foreign_course_and_readers_cannot_manage(self):
        response = self.client.post(self.root + 'comunicados/', {'titulo': 'X', 'cuerpo': 'Y',
            'unidad_educativa': self.other_unit.pk, 'curso': self.course.pk}, format='json')
        self.assertEqual(response.status_code, 403)
        pk = self.draft()
        self.publish(pk)
        self.client.force_authenticate(self.tutor_user)
        self.assertEqual(self.client.patch(f'{self.root}comunicados/{pk}/', {'cuerpo': 'X'}, format='json').status_code, 403)
        self.assertEqual(self.client.post(f'{self.root}comunicados/{pk}/archivar/').status_code, 403)
        self.assertEqual(self.client.post(f'{self.root}comunicados/{pk}/publicar/').status_code, 403)

    def test_institutional_audience_and_snapshot_excludes_later_joiners(self):
        from aplicaciones.comunicacion.models import DestinatarioComunicado
        pk = self.draft(curso=None)
        self.assertEqual(self.publish(pk)['estadisticas']['destinatarios'], 6)
        self.assertFalse(DestinatarioComunicado.objects.filter(comunicado_id=pk, usuario=self.outsider).exists())
        self.outsider.unidad = self.unit
        self.outsider.save(update_fields=['unidad'])
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(f'{self.root}comunicados/{pk}/').status_code, 403)  # perfil inconsistente

    def test_new_attendance_citation_and_transaction_rollback(self):
        from aplicaciones.comunicacion.models import Aviso
        from aplicaciones.estudiantes.models import AsistenciaEstudiante, SesionClase, IncidenteDisciplinario, AccionDisciplinaria
        from aplicaciones.institucion.models import Aula, Modulo
        module = Modulo.objects.create(unidad_educativa=self.unit, nombre='Módulo', cantidad_aulas=1)
        room = Aula.objects.create(modulo=module, nombre='1', capacidad=30)
        session = SesionClase.objects.create(asignacion_docente=self.assignment, fecha='2026-03-01',
            profesor_efectivo=self.prof, aula_efectiva=room)
        attendance = AsistenciaEstudiante.objects.create(sesion_clase=session,
            historial_inscripcion=self.enrollment, estado_asistencia='AUSENTE')
        attendance.save()
        self.assertEqual(Aviso.objects.filter(tipo='FALTA').count(), 2)
        attendance.estado_asistencia = 'ATRASO'
        attendance.save()
        self.assertEqual(Aviso.objects.filter(tipo='ATRASO').count(), 2)
        incident = IncidenteDisciplinario.objects.create(historial_inscripcion=self.enrollment,
            fecha=timezone.now(), tipo='CONDUCTA', severidad='LEVE', descripcion='Descripción privada')
        citation = AccionDisciplinaria.objects.create(incidente=incident, tipo='CITACION',
            tutor_estudiante=self.tutor, fecha_programada=timezone.now())
        citation.save()
        self.assertEqual(Aviso.objects.filter(tipo='CITACION').count(), 2)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                AsistenciaEstudiante.objects.filter(pk=attendance.pk).delete()
                AsistenciaEstudiante.objects.create(sesion_clase=session,
                    historial_inscripcion=self.enrollment, estado_asistencia='AUSENTE')
                raise RuntimeError('rollback')
        self.assertEqual(Aviso.objects.filter(tipo='FALTA').count(), 2)

    def test_low_grade_uses_config_and_rejects_malformed_tenant(self):
        from aplicaciones.academico.models import ResultadoTrimestral
        from aplicaciones.comunicacion.models import Aviso
        self.config.nota_aprobacion = 70
        self.config.save()
        result = ResultadoTrimestral.objects.create(historial_inscripcion=self.enrollment,
            materia=self.subject, periodo=self.period, resultado=65, condicion='REPROBADO', calculado_at=timezone.now())
        self.assertEqual(Aviso.objects.filter(tipo='NOTA_BAJA').count(), 2)
        Aviso.objects.all().delete()
        self.enrollment.unidad = self.other_unit
        self.enrollment.save(update_fields=['unidad'])
        result.save()
        self.assertEqual(Aviso.objects.count(), 0)

    def test_low_grade_accepts_decimal_strings_and_falls_back_to_51(self):
        from aplicaciones.academico.models import ResultadoTrimestral
        from aplicaciones.comunicacion.models import Aviso
        self.config.estado = 'INACTIVO'
        self.config.save(update_fields=['estado'])
        result = ResultadoTrimestral.objects.create(historial_inscripcion=self.enrollment,
            materia=self.subject, periodo=self.period, resultado='51.00', condicion='APROBADO', calculado_at=timezone.now())
        self.assertEqual(Aviso.objects.count(), 0)
        result.resultado = '50.00'
        result.save()
        self.assertEqual(Aviso.objects.filter(tipo='NOTA_BAJA').count(), 2)

    def test_push_network_failure_keeps_durable_inbox(self):
        import requests
        from aplicaciones.usuarios.models import DispositivoNotificacion
        from aplicaciones.comunicacion.models import Aviso
        DispositivoNotificacion.objects.create(usuario=self.student_user, token='ExponentPushToken[failure]', plataforma='ANDROID')
        self.push.side_effect = requests.RequestException('offline')
        with self.assertLogs('aplicaciones.usuarios.notificaciones', level='WARNING'):
            with self.captureOnCommitCallbacks(execute=True):
                pk = self.draft()
                self.publish(pk)
        self.assertEqual(Aviso.objects.filter(comunicado_id=pk).count(), 2)


class ComunicacionConcurrencyTests(SchoolFixture, TransactionTestCase):
    def setUp(self):
        SchoolFixture.setUpTestData.__func__(type(self))

    def test_concurrent_publication_fixes_single_snapshot_and_event_per_user(self):
        from aplicaciones.comunicacion.models import Aviso, Comunicado, DestinatarioComunicado
        from aplicaciones.comunicacion.servicios import publicar
        from aplicaciones.usuarios.models import Usuario
        message = Comunicado.objects.create(titulo='Concurrente', cuerpo='Cuerpo',
            unidad_educativa=self.unit, curso=self.course, creado_por=self.director)
        barrier = Barrier(2)
        def publish_once(_):
            try:
                actor = Usuario.objects.get(pk=self.director.pk)
                barrier.wait(timeout=10)
                return publicar(message.pk, actor).estado
            finally:
                connections.close_all()
        with patch('aplicaciones.comunicacion.servicios._push'):
            with ThreadPoolExecutor(max_workers=2) as executor:
                self.assertEqual(list(executor.map(publish_once, range(2))), ['PUBLICADO', 'PUBLICADO'])
        self.assertEqual(DestinatarioComunicado.objects.filter(comunicado=message).count(), 2)
        self.assertEqual(Aviso.objects.filter(comunicado=message).count(), 2)
        self.assertEqual(EventoAuditoria.objects.filter(entidad='COMUNICADO', entidad_id=str(message.pk)).count(), 1)

    def test_concurrent_alert_events_have_single_notification_per_recipient(self):
        from aplicaciones.comunicacion.models import Aviso
        from aplicaciones.comunicacion.servicios import emitir_alerta_estudiante
        from aplicaciones.estudiantes.models import Estudiante
        barrier = Barrier(2)
        def emit_once(_):
            try:
                student = Estudiante.objects.get(pk=self.student.pk)
                barrier.wait(timeout=10)
                return emitir_alerta_estudiante(estudiante=student, tipo='PAGO', titulo='Pago',
                    cuerpo='Detalle', clave_evento='concurrent-payment')
            finally:
                connections.close_all()
        with patch('aplicaciones.comunicacion.servicios._push'):
            with ThreadPoolExecutor(max_workers=2) as executor:
                self.assertEqual(sum(executor.map(emit_once, range(2))), 2)
        self.assertEqual(Aviso.objects.count(), 2)

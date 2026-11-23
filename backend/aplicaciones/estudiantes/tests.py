from rest_framework import status
from rest_framework.test import APITestCase

from aplicaciones.academico.models import Curso, Grado, Paralelo
from aplicaciones.institucion.models import UnidadEducativa
from aplicaciones.institucion.models import Aula, Colegio, Modulo
from aplicaciones.personal.models import Profesor
from aplicaciones.academico.models import AsignacionDocente, BloqueHorario, HorarioClase
from aplicaciones.usuarios.models import EventoAuditoria, Usuario
from aplicaciones.usuarios.models import Rol
from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from datetime import date, datetime, time
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import (
    AccionDisciplinaria,
    AsistenciaEstudiante,
    Estudiante,
    HistorialInscripcion,
    IncidenteDisciplinario,
    SesionClase,
    Tutor,
    TutorEstudiante,
    DocumentoAcademicoEmitido,
    RiesgoAcademico,
)


class Sprint2Bloque1EstudiantesTests(TestCase):
    def setUp(self):
        self.colegio = Colegio.objects.create(
            nombre='Colegio asistencia', direccion='Local', telefono='70000002',
        )
        self.unidad = UnidadEducativa.objects.create(
            colegio=self.colegio, codigo_sie='SIE-ASISTENCIA', turno='TARDE',
            nombre='Unidad asistencia',
        )
        grado = Grado.objects.create(
            unidad_educativa=self.unidad, nivel_educativo='PRI', numero=2,
        )
        paralelo = Paralelo.objects.create(grado=grado, letra='Y')
        self.curso = Curso.objects.create(paralelo=paralelo, nombre='Segundo Y')
        rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor Bloque 1')
        usuario_profesor = Usuario.objects.create_user(
            ci='PROF-B1', email='prof-b1@example.com', nombre='Profesor', apellido='B1',
            password='Temporal-123', username='prof_b1', fecha_nacimiento='1990-01-01',
            rol=rol_profesor, unidad=self.unidad,
        )
        self.profesor = Profesor.objects.create(usuario=usuario_profesor, unidad=self.unidad)
        self.asignacion = AsignacionDocente.objects.create(
            tipo='TUTOR_CURSO', curso=self.curso, profesor=self.profesor,
            fecha_inicio=date(2026, 2, 1),
        )
        modulo = Modulo.objects.create(
            nombre='Módulo asistencia', cantidad_aulas=1, colegio_fk=self.colegio,
        )
        self.aula = Aula.objects.create(modulo=modulo, nombre='Aula B1', capacidad=30)
        bloque = BloqueHorario.objects.create(
            unidad_educativa=self.unidad, turno='TARDE', dia=1, orden=1,
            hora_inicio=time(14), hora_fin=time(15),
        )
        self.horario = HorarioClase.objects.create(
            asignacion_docente=self.asignacion, profesor=self.profesor, curso=self.curso,
            aula=self.aula, bloque_horario=bloque, fecha_inicio=date(2026, 2, 1),
        )
        rol_estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante Bloque 1')
        usuario_estudiante = Usuario.objects.create_user(
            ci='EST-B1', email='est-b1@example.com', nombre='Estudiante', apellido='B1',
            password='Temporal-123', username='est_b1', fecha_nacimiento='2015-01-01',
            rol=rol_estudiante, unidad=self.unidad,
        )
        self.estudiante = Estudiante.objects.create(
            usuario=usuario_estudiante, rude='RUDE-B1', curso=self.curso, unidad=self.unidad,
        )
        self.historial = HistorialInscripcion.objects.create(
            estudiante=self.estudiante, curso_nuevo=self.curso, unidad=self.unidad,
            usuario_registra=usuario_profesor,
        )

    def crear_sesion(self, fecha=date(2026, 3, 2)):
        return SesionClase.objects.create(
            asignacion_docente=self.asignacion, horario_clase=self.horario,
            fecha=fecha, profesor_efectivo=self.profesor, aula_efectiva=self.aula,
        )

    def test_sesion_clase_evitar_duplicado(self):
        sesion = self.crear_sesion()
        self.assertEqual(sesion.estado, 'PROGRAMADA')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_sesion()

    def test_asistencia_unica_por_sesion_e_inscripcion(self):
        sesion = self.crear_sesion()
        asistencia = AsistenciaEstudiante(
            sesion_clase=sesion, historial_inscripcion=self.historial,
            estado_asistencia='PRESENTE',
        )
        asistencia.full_clean()
        asistencia.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            AsistenciaEstudiante.objects.create(
                sesion_clase=sesion, historial_inscripcion=self.historial,
                estado_asistencia='AUSENTE',
            )

    def test_incidente_disciplinario(self):
        incidente = IncidenteDisciplinario.objects.create(
            historial_inscripcion=self.historial, fecha=timezone.now(),
            tipo='CONDUCTA', severidad='MEDIA', descripcion='Incidente de prueba',
        )
        self.assertEqual(incidente.estado, 'ABIERTO')
        self.assertEqual(incidente.historial_inscripcion, self.historial)

    def test_accion_disciplinaria_valida_tipo_y_tutor(self):
        incidente = IncidenteDisciplinario.objects.create(
            historial_inscripcion=self.historial, fecha=timezone.now(),
            tipo='CONDUCTA', severidad='MEDIA', descripcion='Incidente de prueba',
        )
        rol_tutor, _ = Rol.objects.get_or_create(nombre='Tutor Bloque 1')
        usuario_tutor = Usuario.objects.create_user(
            ci='TUTOR-B1', email='tutor-b1@example.com', nombre='Tutor', apellido='B1',
            password='Temporal-123', username='tutor_b1', fecha_nacimiento='1980-01-01',
            rol=rol_tutor, unidad=self.unidad,
        )
        tutor = Tutor.objects.create(usuario=usuario_tutor)
        relacion = TutorEstudiante.objects.create(tutor=tutor, estudiante=self.estudiante)
        accion = AccionDisciplinaria(
            incidente=incidente, tipo='CITACION', tutor_estudiante=relacion,
            fecha_programada=timezone.now(),
        )
        accion.full_clean()
        accion.save()
        self.assertEqual(accion.estado, 'PENDIENTE')

    def test_documento_academico_reglas_por_tipo(self):
        calendario = CalendarioAcademico.objects.create(unidad_educativa=self.unidad, año=2028, fecha_inicio=date(2028, 2, 1), fecha_fin=date(2028, 11, 30))
        periodo = Periodo.objects.create(calendario=calendario, tipo_division='TRI', nombre='T1', fecha_inicio=date(2028, 2, 1), fecha_fin=date(2028, 5, 1))
        documento = DocumentoAcademicoEmitido(tipo='BOLETIN', historial_inscripcion=self.historial, periodo=periodo, calendario_academico=calendario, version=1, archivo_ref='externo/boletin.pdf', archivo_mime='application/pdf', archivo_tamano=100, archivo_checksum='abc', emitido_at=timezone.now())
        documento.full_clean(); documento.save()
        self.assertIsNone(documento.curso)
        invalido = DocumentoAcademicoEmitido(tipo='CENTRALIZADOR', historial_inscripcion=self.historial, calendario_academico=calendario, version=1, archivo_ref='x', archivo_mime='application/pdf', archivo_tamano=1, archivo_checksum='x', emitido_at=timezone.now())
        with self.assertRaises(ValidationError):
            invalido.full_clean()

    def test_riesgo_academico_abierto_y_resolucion(self):
        riesgo = RiesgoAcademico.objects.create(historial_inscripcion=self.historial, tipo='PROMEDIO', severidad='ALTA', valor_detectado=40, umbral_aplicado=51, regla_version='v1', detectado_at=timezone.now())
        self.assertEqual(riesgo.criterio, {})
        with self.assertRaises(IntegrityError), transaction.atomic():
            RiesgoAcademico.objects.create(historial_inscripcion=self.historial, tipo='PROMEDIO', severidad='ALTA', valor_detectado=39, umbral_aplicado=51, regla_version='v1', detectado_at=timezone.now())


class InscripcionApiTests(APITestCase):
    def setUp(self):
        self.password = 'Clave-Segura-123'
        self.superusuario = Usuario.objects.create_superuser(
            ci='ADMIN-INSCRIPCION',
            email='admin-inscripcion@example.com',
            nombre='Admin',
            apellido='Inscripciones',
            username='admin_inscripciones',
            fecha_nacimiento='1990-01-01',
            password=self.password,
        )
        login = self.client.post(
            '/api/usuarios/login/',
            {'email': self.superusuario.email, 'password': self.password},
            format='json',
        )
        self.authorization = f"Bearer {login.data['access']}"

        self.colegio = Colegio.objects.create(nombre='Colegio de prueba')
        self.unidad = UnidadEducativa.objects.create(
            codigo_sie='SIE-TEST-01',
            turno='TARDE',
            nombre='Unidad de prueba',
            colegio=self.colegio,
        )
        grado = Grado.objects.create(
            unidad_educativa=self.unidad,
            nivel_educativo='PRI',
            numero=1,
        )
        Paralelo.objects.create(grado=grado, letra='A')
        paralelo = Paralelo.objects.create(grado=grado, letra='B')
        self.curso = Curso.objects.create(paralelo=paralelo, nombre='Primero A')
        paralelo_destino = Paralelo.objects.get(grado=grado, letra='A')
        self.curso_destino = Curso.objects.create(
            paralelo=paralelo_destino, nombre='Primero B',
        )

    def _payload_inscripcion(self, *, curso_id=None, unidad_id=None, rude='RUDE-AUD-001'):
        return {
            'nuevo_estudiante': {
                'nombre': 'Auditoria',
                'apellido': 'Inscripcion',
                'ci': f'CI-{rude}',
                'email': f'{rude.lower()}@example.com',
                'sexo': 'F',
                'username': rude.lower(),
                'password': 'Temporal-123',
            },
            'curso_id': curso_id or self.curso.pk,
            'unidad_id': unidad_id or self.unidad.pk,
            'rude': rude,
            'observaciones': '',
        }

    def test_inscripcion_audita_colegio_y_unidad_del_registro_creado(self):
        response = self.client.post(
            '/api/estudiantes/estudiantes/inscribir/',
            self._payload_inscripcion(), format='json',
            HTTP_AUTHORIZATION=self.authorization,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        estudiante = Estudiante.objects.get(rude='RUDE-AUD-001')
        historial = HistorialInscripcion.objects.get(estudiante=estudiante)
        eventos = EventoAuditoria.objects.filter(
            accion='CREAR', entidad='INSCRIPCION', entidad_id=str(historial.pk),
        )
        self.assertEqual(eventos.count(), 1)
        evento = eventos.get()
        self.assertEqual(evento.usuario, self.superusuario.pk)
        self.assertEqual(evento.colegio, self.colegio)
        self.assertEqual(evento.unidad_educativa, self.unidad)
        self.assertIsNotNone(evento.correlacion)
        representacion = str(evento.__dict__)
        for sensible in ('Temporal-123', 'access', 'refresh', 'Authorization', 'headers'):
            self.assertNotIn(sensible, representacion)
        self.assertNotEqual(evento.ip_hash, '127.0.0.1')

    def test_cambio_inscripcion_audita_destino_y_conserva_historial(self):
        creado = self.client.post(
            '/api/estudiantes/estudiantes/inscribir/',
            self._payload_inscripcion(rude='RUDE-AUD-002'), format='json',
            HTTP_AUTHORIZATION=self.authorization,
        )
        self.assertEqual(creado.status_code, status.HTTP_201_CREATED, creado.data)
        estudiante = Estudiante.objects.get(rude='RUDE-AUD-002')
        historial_previo = HistorialInscripcion.objects.get(estudiante=estudiante)

        respuesta = self.client.post(
            f'/api/estudiantes/estudiantes/{estudiante.pk}/cambiar-inscripcion/',
            {
                'curso_id': self.curso_destino.pk,
                'unidad_id': self.unidad.pk,
                'rude': estudiante.rude,
                'observaciones': 'Cambio autorizado',
            },
            format='json', HTTP_AUTHORIZATION=self.authorization,
        )

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        historial = HistorialInscripcion.objects.filter(estudiante=estudiante).latest('pk')
        self.assertNotEqual(historial.pk, historial_previo.pk)
        self.assertEqual(HistorialInscripcion.objects.filter(estudiante=estudiante).count(), 2)
        self.assertTrue(EventoAuditoria.objects.filter(
            accion='CREAR', entidad='INSCRIPCION', entidad_id=str(historial_previo.pk),
        ).exists())
        evento = EventoAuditoria.objects.get(
            accion='ACTUALIZAR', entidad='INSCRIPCION', entidad_id=str(historial.pk),
        )
        self.assertEqual(evento.colegio, self.colegio)
        self.assertEqual(evento.unidad_educativa, self.unidad)
        self.assertEqual(evento.ambito, EventoAuditoria.Ambito.UNIDAD)
        self.assertIsNotNone(evento.correlacion)
        self.assertNotIn('Temporal-123', str(evento.cambios_sanitizados))

    def test_inscribe_y_crea_usuario_sin_id_manual(self):
        response = self.client.post(
            '/api/estudiantes/estudiantes/inscribir/',
            {
                'nuevo_estudiante': {
                    'nombre': 'Ana',
                    'apellido': 'Pérez',
                    'ci': 'CI-EST-001',
                    'email': 'ana.perez@example.com',
                    'sexo': 'F',
                    'username': 'ana.perez',
                    'password': 'Temporal-123',
                },
                'curso_id': self.curso.pk,
                'unidad_id': self.unidad.pk,
                'rude': 'RUDE-TEST-001',
                'observaciones': '',
            },
            format='json',
            HTTP_AUTHORIZATION=self.authorization,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        estudiante = Estudiante.objects.select_related('usuario', 'usuario__rol').get(
            rude='RUDE-TEST-001'
        )
        self.assertEqual(estudiante.usuario.ci, 'CI-EST-001')
        self.assertEqual(estudiante.usuario.rol.nombre, 'Estudiante')
        self.assertTrue(estudiante.usuario.check_password('Temporal-123'))
        self.assertEqual(estudiante.usuario.unidad, self.unidad)
        self.assertEqual(estudiante.curso, self.curso)
        self.assertTrue(HistorialInscripcion.objects.filter(estudiante=estudiante).exists())

        login = self.client.post(
            '/api/usuarios/login/',
            {'email': 'ana.perez@example.com', 'password': 'Temporal-123'},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK, login.data)
        authorization = f"Bearer {login.data['access']}"
        # El catálogo general de cursos es administrativo; el autoservicio del estudiante requerirá un endpoint personal.
        cursos = self.client.get('/api/academico/cursos/', HTTP_AUTHORIZATION=authorization)
        self.assertEqual(cursos.status_code, status.HTTP_403_FORBIDDEN)
        perfil = self.client.get(
            '/api/usuarios/perfil/', HTTP_AUTHORIZATION=authorization
        )
        self.assertEqual(perfil.status_code, status.HTTP_200_OK)
        self.assertEqual(perfil.data['id'], estudiante.usuario_id)
        self.assertEqual(perfil.data['alcance']['tipo'], 'PERSONAL')
        perfil_posterior = self.client.get(
            '/api/usuarios/perfil/', HTTP_AUTHORIZATION=authorization
        )
        self.assertEqual(perfil_posterior.status_code, status.HTTP_200_OK)

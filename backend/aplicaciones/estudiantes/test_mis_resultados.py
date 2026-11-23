from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from aplicaciones.academico.models import (
    ActividadEvaluacion, AsignacionDocente, Calificacion, Curso, DimensionEvaluacion,
    Grado, Materia, MateriaCurso, Paralelo,
)
from aplicaciones.academico.resultados import calcular_resultado_trimestral
from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import Rol, Usuario

from .models import Estudiante, HistorialInscripcion, Tutor, TutorEstudiante


class MisResultadosTests(APITestCase):
    url = '/api/estudiantes/mis-resultados/'
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio = Colegio.objects.create(nombre='Colegio MisResultados', direccion='A', telefono='1')
        cls.unidad = UnidadEducativa.objects.create(
            codigo_sie='MISRES-UA', turno='TARDE', nombre='MISRES-UA', colegio=cls.colegio,
        )
        cls.grado = Grado.objects.create(unidad_educativa=cls.unidad, nivel_educativo='PRI', numero=5)
        cls.paralelo = Paralelo.objects.create(grado=cls.grado, letra='A')
        cls.curso = Curso.objects.create(paralelo=cls.paralelo, nombre='5to A')
        cls.materia = Materia.objects.create(nombre='Ciencias MisResultados')
        cls.materia_curso = MateriaCurso.objects.create(curso=cls.curso, materia=cls.materia)

        cls.gestion = CalendarioAcademico.objects.create(
            unidad_educativa=cls.unidad, año=2026, fecha_inicio=date(2026, 2, 1),
            fecha_fin=date(2026, 11, 30), activo=True,
        )
        cls.periodo = Periodo.objects.create(
            calendario=cls.gestion, tipo_division='TRI', nombre='Trimestre 1',
            fecha_inicio=date(2026, 2, 1), fecha_fin=date(2026, 5, 31), estado='CUR',
        )
        dim_saber = DimensionEvaluacion.objects.get(
            configuracion__calendario_academico=cls.gestion, configuracion__nivel='PRI', codigo='SABER',
        )

        rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        rol_estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante')
        rol_tutor, _ = Rol.objects.get_or_create(nombre='Tutor')

        profesor_usuario = Usuario.objects.create_user(
            ci='MISRES-PRF', email='misres-prf@example.com', nombre='Prof', apellido='MisRes',
            username='misres_prf', fecha_nacimiento='1985-01-01', password=cls.password,
            rol=rol_profesor, unidad=cls.unidad,
        )
        cls.profesor_usuario = profesor_usuario
        profesor = Profesor.objects.create(usuario=profesor_usuario, unidad=cls.unidad)

        asignacion = AsignacionDocente.objects.create(
            tipo='MATERIA', calendario_academico=cls.gestion, curso=cls.curso,
            materia_curso=cls.materia_curso, profesor=profesor, fecha_inicio=date(2026, 2, 10),
        )
        actividad = ActividadEvaluacion.objects.create(
            asignacion_docente=asignacion, periodo=cls.periodo, dimension=dim_saber,
            nombre='Examen MisResultados', fecha=date(2026, 3, 1), puntaje_maximo=Decimal('100'),
        )

        # Estudiante 1: con resultado calculado.
        est1_usuario = Usuario.objects.create_user(
            ci='MISRES-EST1', email='misres-est1@example.com', nombre='Est1', apellido='MisRes',
            username='misres_est1', fecha_nacimiento='2014-01-01', password=cls.password,
            rol=rol_estudiante, unidad=cls.unidad,
        )
        cls.estudiante1 = Estudiante.objects.create(
            usuario=est1_usuario, rude='MISRES-RUDE-1', curso=cls.curso, unidad=cls.unidad,
        )
        cls.estudiante1_usuario = est1_usuario
        cls.historial1 = HistorialInscripcion.objects.create(
            estudiante=cls.estudiante1, curso_nuevo=cls.curso, unidad=cls.unidad, tipo_movimiento='NUEVA',
        )
        Calificacion.objects.create(actividad=actividad, historial_inscripcion=cls.historial1, valor=Decimal('70'))
        calcular_resultado_trimestral(cls.historial1, cls.materia, cls.periodo)

        # Estudiante 2: sin ninguna calificacion (debe salir con trimestrales=[] y anual=None).
        est2_usuario = Usuario.objects.create_user(
            ci='MISRES-EST2', email='misres-est2@example.com', nombre='Est2', apellido='MisRes',
            username='misres_est2', fecha_nacimiento='2014-01-01', password=cls.password,
            rol=rol_estudiante, unidad=cls.unidad,
        )
        cls.estudiante2 = Estudiante.objects.create(
            usuario=est2_usuario, rude='MISRES-RUDE-2', curso=cls.curso, unidad=cls.unidad,
        )
        HistorialInscripcion.objects.create(
            estudiante=cls.estudiante2, curso_nuevo=cls.curso, unidad=cls.unidad, tipo_movimiento='NUEVA',
        )

        # Tutor con dos hijos (estudiante1 y estudiante2).
        tutor_usuario = Usuario.objects.create_user(
            ci='MISRES-TUT', email='misres-tut@example.com', nombre='Tut', apellido='MisRes',
            username='misres_tut', fecha_nacimiento='1980-01-01', password=cls.password,
            rol=rol_tutor, unidad=cls.unidad,
        )
        cls.tutor_usuario = tutor_usuario
        tutor = Tutor.objects.create(usuario=tutor_usuario, parentesco='PAD')
        TutorEstudiante.objects.create(tutor=tutor, estudiante=cls.estudiante1, es_principal=True)
        TutorEstudiante.objects.create(tutor=tutor, estudiante=cls.estudiante2, es_principal=False)

        # Tutor con un solo hijo (estudiante1), para el caso "sin ambiguedad".
        tutor_unico_usuario = Usuario.objects.create_user(
            ci='MISRES-TUTU', email='misres-tutu@example.com', nombre='TutU', apellido='MisRes',
            username='misres_tutu', fecha_nacimiento='1980-01-01', password=cls.password,
            rol=rol_tutor, unidad=cls.unidad,
        )
        cls.tutor_unico_usuario = tutor_unico_usuario
        tutor_unico = Tutor.objects.create(usuario=tutor_unico_usuario, parentesco='MAD')
        TutorEstudiante.objects.create(tutor=tutor_unico, estudiante=cls.estudiante1, es_principal=False)

    def autenticar(self, usuario):
        self.client.force_authenticate(usuario)

    def test_anonimo_no_puede_acceder(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_profesor_no_tiene_acceso_a_este_endpoint(self):
        self.autenticar(self.profesor_usuario)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_estudiante_ve_sus_propios_resultados(self):
        self.autenticar(self.estudiante1_usuario)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['estudiante'], self.estudiante1.pk)
        materia = respuesta.data['materias'][0]
        self.assertEqual(materia['materia'], self.materia.pk)
        self.assertEqual(len(materia['trimestrales']), 1)
        self.assertEqual(materia['trimestrales'][0]['resultado'], '25.00')
        self.assertIsNotNone(materia['anual'])

    def test_estudiante_sin_calificaciones_no_falla(self):
        self.autenticar(Usuario.objects.get(pk=self.estudiante2.pk))
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        materia = respuesta.data['materias'][0]
        self.assertEqual(materia['trimestrales'], [])
        self.assertIsNone(materia['anual'])

    def test_estudiante_no_puede_pedir_el_resultado_de_otro(self):
        self.autenticar(self.estudiante1_usuario)
        respuesta = self.client.get(self.url, {'estudiante': self.estudiante2.pk})
        self.assertEqual(respuesta.status_code, 403)

    def test_tutor_con_un_solo_hijo_no_necesita_el_parametro(self):
        self.autenticar(self.tutor_unico_usuario)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['estudiante'], self.estudiante1.pk)

    def test_tutor_con_varios_hijos_sin_parametro_pide_que_elija(self):
        self.autenticar(self.tutor_usuario)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 400)
        hijos = {fila['estudiante'] for fila in respuesta.data['hijos']}
        self.assertEqual(hijos, {self.estudiante1.pk, self.estudiante2.pk})

    def test_tutor_con_varios_hijos_puede_elegir_cual_ver(self):
        self.autenticar(self.tutor_usuario)
        respuesta = self.client.get(self.url, {'estudiante': self.estudiante2.pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['estudiante'], self.estudiante2.pk)

    def test_tutor_no_puede_ver_a_un_estudiante_que_no_es_su_hijo(self):
        self.autenticar(self.tutor_unico_usuario)
        respuesta = self.client.get(self.url, {'estudiante': self.estudiante2.pk})
        self.assertEqual(respuesta.status_code, 403)

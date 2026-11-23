from datetime import date

from rest_framework.test import APITestCase

from aplicaciones.academico.models import Curso, Grado, Materia, MateriaCurso, Paralelo
from aplicaciones.estudiantes.models import Estudiante, Tutor, TutorEstudiante
from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import Admin, Puesto, Rol, Usuario

from .models import DetalleAsistencia, RegistroAsistencia


class AsistenciaAlcanceLecturaTests(APITestCase):
    """HU-13: nadie autenticado debe poder leer la asistencia de un
    estudiante ajeno. Antes de esta correccion, list/retrieve/resumen solo
    exigian IsAuthenticated y no filtraban por pertenencia (IDOR)."""

    url_registros = '/api/asistencia/registros/'
    url_detalles = '/api/asistencia/detalles/'
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio = Colegio.objects.create(nombre='Colegio Asistencia', direccion='A', telefono='1')
        cls.unidad = UnidadEducativa.objects.create(
            codigo_sie='ASIS-UA', turno='TARDE', nombre='ASIS-UA', colegio=cls.colegio,
        )
        cls.grado = Grado.objects.create(unidad_educativa=cls.unidad, nivel_educativo='PRI', numero=2)
        cls.paralelo = Paralelo.objects.create(grado=cls.grado, letra='A')
        cls.curso = Curso.objects.create(paralelo=cls.paralelo, nombre='2do A')
        cls.materia = Materia.objects.create(nombre='Lenguaje Asistencia')

        rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        rol_estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante')
        rol_tutor, _ = Rol.objects.get_or_create(nombre='Tutor')

        cls.superusuario = Usuario.objects.create_superuser(
            ci='ASIS-SUP', email='asis-sup@example.com', nombre='Super', apellido='Asis',
            username='asis_sup', fecha_nacimiento='1990-01-01', password=cls.password,
        )

        profesor_a_usuario = Usuario.objects.create_user(
            ci='ASIS-PA', email='asis-pa@example.com', nombre='ProfA', apellido='Asis',
            username='asis_profa', fecha_nacimiento='1985-01-01', password=cls.password,
            rol=rol_profesor, unidad=cls.unidad,
        )
        cls.profesor_a = Profesor.objects.create(usuario=profesor_a_usuario, unidad=cls.unidad)
        cls.profesor_a_usuario = profesor_a_usuario
        cls.materia_curso = MateriaCurso.objects.create(curso=cls.curso, materia=cls.materia, profesor=cls.profesor_a)

        profesor_b_usuario = Usuario.objects.create_user(
            ci='ASIS-PB', email='asis-pb@example.com', nombre='ProfB', apellido='Asis',
            username='asis_profb', fecha_nacimiento='1985-01-01', password=cls.password,
            rol=rol_profesor, unidad=cls.unidad,
        )
        cls.profesor_b = Profesor.objects.create(usuario=profesor_b_usuario, unidad=cls.unidad)
        cls.profesor_b_usuario = profesor_b_usuario

        director_usuario = Usuario.objects.create_user(
            ci='ASIS-DIR', email='asis-dir@example.com', nombre='Dir', apellido='Asis',
            username='asis_dir', fecha_nacimiento='1980-01-01', password=cls.password,
            rol=rol_admin, unidad=cls.unidad,
        )
        puesto, _ = Puesto.objects.get_or_create(nombre='Director')
        Admin.objects.create(usuario=director_usuario, unidad=cls.unidad, puesto=puesto)
        cls.director = director_usuario

        est1_usuario = Usuario.objects.create_user(
            ci='ASIS-EST1', email='asis-est1@example.com', nombre='Est1', apellido='Asis',
            username='asis_est1', fecha_nacimiento='2015-01-01', password=cls.password,
            rol=rol_estudiante, unidad=cls.unidad,
        )
        cls.estudiante1 = Estudiante.objects.create(
            usuario=est1_usuario, rude='ASIS-RUDE-1', curso=cls.curso, unidad=cls.unidad,
        )
        cls.estudiante1_usuario = est1_usuario

        est2_usuario = Usuario.objects.create_user(
            ci='ASIS-EST2', email='asis-est2@example.com', nombre='Est2', apellido='Asis',
            username='asis_est2', fecha_nacimiento='2015-01-01', password=cls.password,
            rol=rol_estudiante, unidad=cls.unidad,
        )
        cls.estudiante2 = Estudiante.objects.create(
            usuario=est2_usuario, rude='ASIS-RUDE-2', curso=cls.curso, unidad=cls.unidad,
        )

        tutor1_usuario = Usuario.objects.create_user(
            ci='ASIS-TUT1', email='asis-tut1@example.com', nombre='Tut1', apellido='Asis',
            username='asis_tut1', fecha_nacimiento='1980-01-01', password=cls.password,
            rol=rol_tutor, unidad=cls.unidad,
        )
        cls.tutor1 = Tutor.objects.create(usuario=tutor1_usuario, parentesco='PAD')
        cls.tutor1_usuario = tutor1_usuario
        TutorEstudiante.objects.create(tutor=cls.tutor1, estudiante=cls.estudiante1, es_principal=True)

        cls.registro = RegistroAsistencia.objects.create(
            asignacion=cls.materia_curso, fecha=date(2026, 3, 2), docente=profesor_a_usuario,
        )
        cls.detalle1 = DetalleAsistencia.objects.create(
            registro=cls.registro, estudiante=cls.estudiante1, estado='P',
        )
        cls.detalle2 = DetalleAsistencia.objects.create(
            registro=cls.registro, estudiante=cls.estudiante2, estado='A',
        )

    def autenticar(self, usuario):
        self.client.force_authenticate(usuario)

    # --- Sin autenticar ---

    def test_anonimo_no_puede_listar_registros(self):
        self.assertEqual(self.client.get(self.url_registros).status_code, 401)

    def test_anonimo_no_puede_listar_detalles(self):
        self.assertEqual(self.client.get(self.url_detalles).status_code, 401)

    # --- Gestion / profesor: acceso legitimo intacto ---

    def test_director_ve_todos_los_detalles(self):
        self.autenticar(self.director)
        respuesta = self.client.get(self.url_detalles)
        self.assertEqual(respuesta.status_code, 200)
        ids = {fila['id'] for fila in respuesta.data}
        self.assertEqual(ids, {self.detalle1.pk, self.detalle2.pk})

    def test_profesor_asignado_ve_su_registro_completo(self):
        self.autenticar(self.profesor_a_usuario)
        respuesta = self.client.get(self.url_registros)
        self.assertEqual(respuesta.status_code, 200)
        ids = {fila['id'] for fila in respuesta.data}
        self.assertIn(self.registro.pk, ids)

    def test_profesor_no_asignado_no_ve_el_registro(self):
        self.autenticar(self.profesor_b_usuario)
        respuesta = self.client.get(self.url_registros)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, [])

    # --- El hueco de seguridad original: tutor/estudiante ---

    def test_tutor_no_ve_registro_de_cabecera_ni_de_companeros(self):
        """RegistroAsistencia anida TODOS los detalles de la clase; tutor
        debe quedar vacio aqui aunque su hijo este en ese registro."""
        self.autenticar(self.tutor1_usuario)
        respuesta = self.client.get(self.url_registros)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, [])

    def test_tutor_solo_ve_el_detalle_de_su_hijo(self):
        self.autenticar(self.tutor1_usuario)
        respuesta = self.client.get(self.url_detalles)
        self.assertEqual(respuesta.status_code, 200)
        ids = {fila['id'] for fila in respuesta.data}
        self.assertEqual(ids, {self.detalle1.pk})

    def test_tutor_no_puede_forzar_ver_a_otro_estudiante_por_query_param(self):
        """Antes de la correccion, cualquier autenticado podia pasar
        ?estudiante=<id> y leer la asistencia de otro estudiante."""
        self.autenticar(self.tutor1_usuario)
        respuesta = self.client.get(self.url_detalles, {'estudiante': self.estudiante2.pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, [])

    def test_estudiante_solo_ve_su_propio_detalle(self):
        self.autenticar(self.estudiante1_usuario)
        respuesta = self.client.get(self.url_detalles)
        self.assertEqual(respuesta.status_code, 200)
        ids = {fila['id'] for fila in respuesta.data}
        self.assertEqual(ids, {self.detalle1.pk})

    def test_estudiante_no_ve_registro_de_cabecera(self):
        self.autenticar(self.estudiante1_usuario)
        respuesta = self.client.get(self.url_registros)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, [])

    def test_resumen_de_tutor_solo_cuenta_a_su_hijo(self):
        self.autenticar(self.tutor1_usuario)
        respuesta = self.client.get(f'{self.url_detalles}resumen/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data), 1)
        self.assertEqual(respuesta.data[0]['estudiante'], self.estudiante1.pk)

    # --- La accion 'estudiantes' (roster) es solo para quien gestiona/registra ---

    def test_tutor_no_puede_listar_el_roster_del_curso(self):
        self.autenticar(self.tutor1_usuario)
        respuesta = self.client.get(f'{self.url_registros}estudiantes/', {'curso': self.curso.pk})
        self.assertEqual(respuesta.status_code, 403)

    def test_profesor_asignado_si_puede_listar_el_roster(self):
        self.autenticar(self.profesor_a_usuario)
        respuesta = self.client.get(f'{self.url_registros}estudiantes/', {'curso': self.curso.pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data), 2)

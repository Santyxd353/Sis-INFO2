from datetime import date

from rest_framework.test import APITestCase

from aplicaciones.calendario.models import CalendarioAcademico
from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import (
    Accion, Admin, ModeloPermitido, PermisoPuesto, PermisoRol, Rol, Usuario,
)

from .models import Curso, Grado, Paralelo


def ids(response):
    data = response.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return {row['id'] for row in rows}


class CatalogosPorUnidadHU11Tests(APITestCase):
    profesores_url = '/api/personal/profesores/'
    calendarios_url = '/api/calendario/calendarios/'
    cursos_url = '/api/academico/cursos/'
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio_a = Colegio.objects.create(nombre='Colegio A catálogos', direccion='A', telefono='1')
        cls.colegio_b = Colegio.objects.create(nombre='Colegio B catálogos', direccion='B', telefono='2')
        cls.a1 = cls.unidad('CAT-A1', cls.colegio_a)
        cls.a2 = cls.unidad('CAT-A2', cls.colegio_a)
        cls.b1 = cls.unidad('CAT-B1', cls.colegio_b)

        cls.rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        cls.rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        cls.rol_estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante')
        cls.superadmin = Usuario.objects.create_superuser(
            ci='CAT-SUP', email='cat-sup@example.com', nombre='Super', apellido='Cat',
            username='cat_sup', fecha_nacimiento='1990-01-01', password=cls.password,
        )
        cls.director = cls.admin('CAT-DIR', cls.a1, 'Director')
        cls.secretaria = cls.admin('CAT-SEC', cls.a1, 'Secretaria')
        cls.estudiante = cls.usuario('CAT-EST', cls.a1, cls.rol_estudiante)
        cls.profesor_a1 = cls.profesor('CAT-PA1', cls.a1)
        cls.profesor_a2 = cls.profesor('CAT-PA2', cls.a2)
        cls.profesor_b1 = cls.profesor('CAT-PB1', cls.b1)

        cls.cal_a1 = cls.calendario(cls.a1, 2026)
        cls.cal_a2 = cls.calendario(cls.a2, 2026)
        cls.cal_b1 = cls.calendario(cls.b1, 2026)
        cls.curso_a1, cls.paralelo_a1 = cls.curso(cls.a1, 'A')
        cls.curso_a2, cls.paralelo_a2 = cls.curso(cls.a2, 'B')
        cls.curso_b1, cls.paralelo_b1 = cls.curso(cls.b1, 'C')

        accion, _ = Accion.objects.get_or_create(nombre='listar')
        for modelo_nombre in ('profesor', 'calendario', 'curso'):
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=modelo_nombre)
            for admin in (cls.director, cls.secretaria):
                PermisoPuesto.objects.get_or_create(
                    puesto=admin.admin.puesto, modelo=modelo, accion=accion,
                )
            if modelo_nombre == 'profesor':
                PermisoRol.objects.get_or_create(
                    rol=cls.rol_profesor, modelo=modelo, accion=accion,
                )

    @classmethod
    def unidad(cls, codigo, colegio):
        return UnidadEducativa.objects.create(
            codigo_sie=codigo, turno='TARDE', nombre=codigo, colegio=colegio,
        )

    @classmethod
    def usuario(cls, codigo, unidad, rol):
        return Usuario.objects.create_user(
            ci=codigo, email=f'{codigo.lower()}@example.com', nombre=codigo,
            apellido='Catálogo', username=codigo.lower(), fecha_nacimiento='1990-01-01',
            password=cls.password, rol=rol, unidad=unidad,
        )

    @classmethod
    def admin(cls, codigo, unidad, puesto):
        usuario = cls.usuario(codigo, unidad, cls.rol_admin)
        from aplicaciones.usuarios.models import Puesto
        cargo, _ = Puesto.objects.get_or_create(nombre=puesto)
        Admin.objects.create(usuario=usuario, unidad=unidad, colegio=unidad.colegio, puesto=cargo)
        return usuario

    @classmethod
    def profesor(cls, codigo, unidad):
        return Profesor.objects.create(usuario=cls.usuario(codigo, unidad, cls.rol_profesor), unidad=unidad)

    @staticmethod
    def calendario(unidad, anio):
        return CalendarioAcademico.objects.create(
            unidad_educativa=unidad, año=anio, fecha_inicio=date(anio, 2, 1),
            fecha_fin=date(anio, 11, 30), activo=True,
        )

    @staticmethod
    def curso(unidad, letra):
        grado = Grado.objects.create(unidad_educativa=unidad, nivel_educativo='PRI', numero=1)
        paralelo = Paralelo.objects.create(grado=grado, letra=letra)
        return Curso.objects.create(paralelo=paralelo, nombre=f'Curso {letra}'), paralelo

    def autenticar(self, usuario):
        self.client.force_authenticate(usuario)

    def test_profesores_sin_parametro_conserva_el_alcance_del_director(self):
        self.autenticar(self.director)
        response = self.client.get(self.profesores_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ids(response), {self.profesor_a1.pk, self.profesor_a2.pk})

    def test_profesores_director_filtra_unidades_del_colegio(self):
        self.autenticar(self.director)
        for unidad, esperado in ((self.a1, self.profesor_a1), (self.a2, self.profesor_a2)):
            with self.subTest(unidad=unidad.pk):
                response = self.client.get(self.profesores_url, {'unidad': unidad.pk})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(ids(response), {esperado.pk})

    def test_profesores_no_amplian_el_alcance_de_director_o_secretaria(self):
        self.autenticar(self.director)
        self.assertEqual(ids(self.client.get(self.profesores_url, {'unidad': self.b1.pk})), set())
        self.autenticar(self.secretaria)
        self.assertEqual(ids(self.client.get(self.profesores_url, {'unidad': self.a1.pk})), {self.profesor_a1.pk})
        self.assertEqual(ids(self.client.get(self.profesores_url, {'unidad': self.a2.pk})), set())

    def test_profesores_superadmin_puede_filtrar_b1(self):
        self.autenticar(self.superadmin)
        response = self.client.get(self.profesores_url, {'unidad': self.b1.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ids(response), {self.profesor_b1.pk})

    def test_profesor_no_amplia_su_ambito_personal_con_el_filtro(self):
        self.autenticar(self.profesor_a1.usuario)
        self.assertEqual(
            ids(self.client.get(self.profesores_url, {'unidad': self.a1.pk})),
            {self.profesor_a1.pk},
        )
        self.assertEqual(ids(self.client.get(self.profesores_url, {'unidad': self.a2.pk})), set())

    def test_profesores_unidad_invalida_responde_400(self):
        self.autenticar(self.director)
        for valor in ('texto', '0', '-1', '1.5'):
            with self.subTest(valor=valor):
                response = self.client.get(self.profesores_url, {'unidad': valor})
                self.assertEqual(response.status_code, 400)
                self.assertIn('unidad', response.data)

    def test_calendarios_director_y_secretaria_respetan_unidad(self):
        self.autenticar(self.director)
        self.assertEqual(ids(self.client.get(self.calendarios_url, {'unidad_educativa': self.a1.pk})), {self.cal_a1.pk})
        self.assertEqual(ids(self.client.get(self.calendarios_url, {'unidad_educativa': self.a2.pk})), {self.cal_a2.pk})
        self.assertEqual(ids(self.client.get(self.calendarios_url, {'unidad_educativa': self.b1.pk})), set())
        self.autenticar(self.secretaria)
        self.assertEqual(ids(self.client.get(self.calendarios_url, {'unidad_educativa': self.a1.pk})), {self.cal_a1.pk})
        self.assertEqual(ids(self.client.get(self.calendarios_url, {'unidad_educativa': self.a2.pk})), set())

    def test_calendarios_superadmin_e_invalidos(self):
        self.autenticar(self.superadmin)
        self.assertEqual(ids(self.client.get(self.calendarios_url, {'unidad_educativa': self.b1.pk})), {self.cal_b1.pk})
        for valor in ('texto', '0', '-1', '1.5'):
            with self.subTest(valor=valor):
                response = self.client.get(self.calendarios_url, {'unidad_educativa': valor})
                self.assertEqual(response.status_code, 400)
                self.assertIn('unidad_educativa', response.data)

    def test_cursos_director_y_secretaria_respetan_unidad(self):
        self.autenticar(self.director)
        self.assertEqual(ids(self.client.get(self.cursos_url, {'unidad_educativa': self.a1.pk})), {self.curso_a1.pk})
        self.assertEqual(ids(self.client.get(self.cursos_url, {'unidad_educativa': self.a2.pk})), {self.curso_a2.pk})
        self.assertEqual(ids(self.client.get(self.cursos_url, {'unidad_educativa': self.b1.pk})), set())
        self.autenticar(self.secretaria)
        self.assertEqual(ids(self.client.get(self.cursos_url, {'unidad_educativa': self.a1.pk})), {self.curso_a1.pk})
        self.assertEqual(ids(self.client.get(self.cursos_url, {'unidad_educativa': self.a2.pk})), set())

    def test_cursos_superadmin_combina_unidad_y_paralelo(self):
        self.autenticar(self.superadmin)
        self.assertEqual(ids(self.client.get(self.cursos_url, {'unidad_educativa': self.b1.pk})), {self.curso_b1.pk})
        self.assertEqual(ids(self.client.get(self.cursos_url, {
            'unidad_educativa': self.a1.pk, 'paralelo': self.paralelo_a1.pk,
        })), {self.curso_a1.pk})
        self.assertEqual(ids(self.client.get(self.cursos_url, {
            'unidad_educativa': self.a1.pk, 'paralelo': self.paralelo_a2.pk,
        })), set())

    def test_cursos_estudiante_continua_sin_acceso(self):
        self.autenticar(self.estudiante)
        self.assertEqual(self.client.get(self.cursos_url).status_code, 403)

    def test_cursos_estudiante_inscrito_denegado_antes_del_queryset(self):
        from unittest.mock import patch

        Estudiante.objects.create(usuario=self.estudiante, rude='CAT-RUDE', unidad=self.a1, curso=self.curso_a1)
        self.autenticar(self.estudiante)
        consultas = (
            (self.cursos_url, {}),
            (f'{self.cursos_url}{self.curso_a1.pk}/', {}),
            (self.cursos_url, {'unidad_educativa': self.a1.pk}),
            (self.cursos_url, {'paralelo': self.paralelo_a1.pk}),
        )
        with patch('aplicaciones.academico.views.CursoViewSet.get_queryset', side_effect=AssertionError('No debe consultar cursos')):
            for url, params in consultas:
                with self.subTest(url=url, params=params):
                    response = self.client.get(url, params)
                    self.assertEqual(response.status_code, 403)
                    self.assertNotIn('results', response.data)
                    self.assertNotIn('count', response.data)
                    self.assertNotIn('Curso A', str(response.data))

    def test_cursos_denegacion_no_invalida_jwt(self):
        login = self.client.post('/api/usuarios/login/', {
            'email': self.estudiante.email, 'password': self.password,
        }, format='json')
        self.assertEqual(login.status_code, 200)
        authorization = f"Bearer {login.data['access']}"
        self.assertEqual(self.client.get(self.cursos_url, HTTP_AUTHORIZATION=authorization).status_code, 403)
        self.assertEqual(self.client.get('/api/usuarios/perfil/', HTTP_AUTHORIZATION=authorization).status_code, 200)
        self.assertEqual(self.client.get('/api/usuarios/perfil/', HTTP_AUTHORIZATION=authorization).status_code, 200)

    def test_cursos_sin_autenticacion_y_profesor_con_alcance_personal(self):
        self.assertEqual(self.client.get(self.cursos_url).status_code, 401)
        self.curso_a1.tutor = self.profesor_a1
        self.curso_a1.save(update_fields=['tutor'])
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='curso')
        PermisoRol.objects.get_or_create(rol=self.rol_profesor, modelo=modelo, accion=accion)
        self.autenticar(self.profesor_a1.usuario)
        self.assertEqual(ids(self.client.get(self.cursos_url)), {self.curso_a1.pk})
        self.assertEqual(ids(self.client.get(self.cursos_url, {'unidad_educativa': self.a2.pk})), set())
        self.assertEqual(ids(self.client.get(self.cursos_url, {'paralelo': self.paralelo_a2.pk})), set())

    def test_cursos_unidad_invalida_responde_400(self):
        self.autenticar(self.director)
        for valor in ('texto', '0', '-1', '1.5'):
            with self.subTest(valor=valor):
                response = self.client.get(self.cursos_url, {'unidad_educativa': valor})
                self.assertEqual(response.status_code, 400)
                self.assertIn('unidad_educativa', response.data)

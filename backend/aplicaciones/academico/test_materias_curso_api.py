from datetime import date

from rest_framework.test import APITestCase

from aplicaciones.calendario.models import CalendarioAcademico
from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import (
    Accion, Admin, EventoAuditoria, ModeloPermitido, PermisoPuesto, Puesto, Rol,
    Usuario,
)

from .models import Curso, Grado, Materia, MateriaCurso, Paralelo


class MateriaCursoConsultaApiTests(APITestCase):
    url = '/api/academico/materias-curso/'
    materias_url = '/api/academico/materias/'
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio_a = Colegio.objects.create(nombre='Colegio MC A', direccion='A', telefono='1')
        cls.colegio_b = Colegio.objects.create(nombre='Colegio MC B', direccion='B', telefono='2')
        cls.ua = cls._unidad('MC-UA', cls.colegio_a)
        cls.ua2 = cls._unidad('MC-UA2', cls.colegio_a)
        cls.ub = cls._unidad('MC-UB', cls.colegio_b)
        cls.u_heredada = cls._unidad('MC-UH', None)
        cls.curso_a, cls.mc_a, cls.mc_a_extra = cls._curso(cls.ua, 'A')
        cls.curso_a2, cls.mc_a2, _ = cls._curso(cls.ua2, 'B')
        cls.curso_b, cls.mc_b, _ = cls._curso(cls.ub, 'C')
        cls.curso_h, cls.mc_h, _ = cls._curso(cls.u_heredada, 'D')
        cls.superusuario = Usuario.objects.create_superuser(
            ci='MC-SUP', email='mc-sup@example.com', nombre='Super', apellido='MC',
            username='mc_sup', fecha_nacimiento='1990-01-01', password=cls.password,
        )
        rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        rol_tutor, _ = Rol.objects.get_or_create(nombre='Tutor')
        cls.director = cls._admin('DIR', cls.ua, rol_admin, 'Director')
        cls.secretaria = cls._admin('SEC', cls.ua, rol_admin, 'Secretaria')
        cls.admin = cls._admin('ADM', cls.ua, rol_admin, 'Administrador institucional')
        cls.admin_heredado = cls._admin('HER', cls.u_heredada, rol_admin, 'Administrador institucional')
        cls.profesor = Profesor.objects.create(
            usuario=cls._usuario('PROF', cls.ua, rol_profesor), unidad=cls.ua,
        )
        cls.sin_permiso = cls._usuario('TUT', cls.ua, rol_tutor)
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='asignacion-docente')
        listar, _ = Accion.objects.get_or_create(nombre='listar')
        for usuario in (cls.director, cls.secretaria, cls.admin, cls.admin_heredado):
            PermisoPuesto.objects.get_or_create(
                puesto=usuario.admin.puesto, modelo=modelo, accion=listar,
            )

    @classmethod
    def _unidad(cls, codigo, colegio):
        return UnidadEducativa.objects.create(
            codigo_sie=codigo, turno='TARDE', nombre=codigo, colegio=colegio,
        )

    @classmethod
    def _curso(cls, unidad, letra):
        grado = Grado.objects.create(unidad_educativa=unidad, nivel_educativo='PRI', numero=1)
        paralelo = Paralelo.objects.create(grado=grado, letra=letra)
        curso = Curso.objects.create(paralelo=paralelo, nombre=f'Curso {letra}')
        materia = Materia.objects.create(nombre=f'Materia MC {letra}')
        extra = Materia.objects.create(nombre=f'Z Materia MC {letra}')
        return (
            curso,
            MateriaCurso.objects.create(curso=curso, materia=materia),
            MateriaCurso.objects.create(curso=curso, materia=extra),
        )

    @classmethod
    def _usuario(cls, codigo, unidad, rol):
        return Usuario.objects.create_user(
            ci=f'MC-{codigo}', email=f'mc-{codigo.lower()}@example.com',
            nombre=codigo, apellido='MC', username=f'mc_{codigo.lower()}',
            fecha_nacimiento='1990-01-01', password=cls.password, rol=rol, unidad=unidad,
        )

    @classmethod
    def _admin(cls, codigo, unidad, rol, puesto):
        usuario = cls._usuario(codigo, unidad, rol)
        cargo, _ = Puesto.objects.get_or_create(nombre=puesto)
        Admin.objects.create(usuario=usuario, unidad=unidad, colegio=unidad.colegio, puesto=cargo)
        return usuario

    def auth(self, usuario=None):
        self.client.force_authenticate(usuario or self.superusuario)

    def test_no_autenticado_recibe_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_usuario_sin_permiso_recibe_403(self):
        self.auth(self.sin_permiso)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_superadmin_consulta_todos(self):
        self.auth()
        self.assertEqual(self.client.get(self.url).data['count'], 8)

    def test_admin_institucional_sin_permiso_es_rechazado(self):
        from aplicaciones.usuarios.models import PermisoRol
        PermisoPuesto.objects.filter(puesto=self.admin.admin.puesto, modelo__nombre='materia-curso', accion__nombre='listar').delete()
        PermisoRol.objects.filter(rol=self.admin.rol, modelo__nombre='materia-curso', accion__nombre='listar').delete()
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_director_limitado_a_colegio(self):
        self.auth(self.director)
        self.assertEqual(self.client.get(self.url).data['count'], 4)

    def test_secretaria_limitada_a_unidad(self):
        self.auth(self.secretaria)
        self.assertEqual(self.client.get(self.url).data['count'], 2)

    def test_profesor_solo_consulta_materias_de_asignaciones_propias(self):
        self.auth(self.profesor.usuario)
        self.assertEqual(self.client.get(self.url).data['count'], 0)

    def test_filtro_por_curso(self):
        self.auth()
        response = self.client.get(self.url, {'curso': self.curso_a.pk})
        self.assertEqual({x['id'] for x in response.data['results']}, {self.mc_a.pk, self.mc_a_extra.pk})

    def test_filtro_por_materia(self):
        self.auth()
        response = self.client.get(self.url, {'materia': self.mc_a.materia_id})
        self.assertEqual([x['id'] for x in response.data['results']], [self.mc_a.pk])

    def test_curso_ajeno_no_amplia_alcance(self):
        self.auth(self.director)
        response = self.client.get(self.url, {'curso': self.curso_b.pk})
        self.assertEqual(response.data['count'], 0)

    def test_curso_invalido_responde_400(self):
        self.auth()
        self.assertEqual(self.client.get(self.url, {'curso': 'x'}).status_code, 400)

    def test_materia_invalida_responde_400(self):
        self.auth()
        self.assertEqual(self.client.get(self.url, {'materia': '0'}).status_code, 400)

    def test_superadmin_no_recibe_crud_implicito(self):
        self.auth()
        self.assertEqual(self.client.post(self.url, {}).status_code, 403)

    def test_superadmin_no_recibe_edicion_implicita(self):
        self.auth()
        self.assertEqual(self.client.patch(f'{self.url}{self.mc_a.pk}/', {}).status_code, 403)

    def test_delete_fisico_no_esta_habilitado(self):
        self.auth()
        self.assertEqual(self.client.delete(f'{self.url}{self.mc_a.pk}/').status_code, 403)

    def test_respuesta_contiene_contrato_minimo(self):
        self.auth()
        data = self.client.get(f'{self.url}{self.mc_a.pk}/').data
        self.assertTrue({'id', 'curso', 'curso_nombre', 'materia', 'materia_nombre'} <= set(data))

    def test_director_crea_materias_en_unidades_de_su_colegio(self):
        self.auth(self.director)
        primera = self.client.post(self.materias_url, {'unidad_educativa': self.ua.pk, 'nombre': '  Física   aplicada '}, format='json')
        segunda = self.client.post(self.materias_url, {'unidad_educativa': self.ua2.pk, 'nombre': 'Física aplicada'}, format='json')
        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(segunda.status_code, 201, segunda.data)
        self.assertEqual(primera.data['nombre'], 'Física aplicada')

    def test_nombre_case_insensitive_se_rechaza_en_misma_unidad(self):
        self.auth(self.director)
        self.assertEqual(self.client.post(self.materias_url, {'unidad_educativa': self.ua.pk, 'nombre': 'Biología'}, format='json').status_code, 201)
        repetida = self.client.post(self.materias_url, {'unidad_educativa': self.ua.pk, 'nombre': '  biología  '}, format='json')
        self.assertEqual(repetida.status_code, 400)

    def test_secretaria_no_puede_crear_en_unidad_hermana(self):
        self.auth(self.secretaria)
        response = self.client.post(self.materias_url, {'unidad_educativa': self.ua2.pk, 'nombre': 'Química'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_materia_curso_rechaza_materia_de_otra_unidad(self):
        materia = Materia.objects.create(nombre='Externa', unidad_educativa=self.ub)
        self.auth(self.director)
        response = self.client.post(self.url, {'curso': self.curso_a.pk, 'materia': materia.pk}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_creacion_materia_audita(self):
        self.auth(self.director)
        response = self.client.post(self.materias_url, {'unidad_educativa': self.ua.pk, 'nombre': 'Auditable'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(EventoAuditoria.objects.filter(entidad='MATERIA', entidad_id=str(response.data['id']), accion='CREAR').exists())

    def test_id_es_compatible_con_asignacion_docente(self):
        gestion = CalendarioAcademico.objects.create(
            unidad_educativa=self.ua, año=2026, fecha_inicio=date(2026, 2, 1),
            fecha_fin=date(2026, 11, 30), activo=True,
        )
        self.auth()
        response = self.client.post('/api/academico/asignaciones-docentes/', {
            'tipo': 'MATERIA', 'calendario_academico': gestion.pk,
            'curso': self.curso_a.pk, 'materia_curso': self.mc_a.pk,
            'profesor': self.profesor.pk, 'fecha_inicio': '2026-02-10',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_paginacion_para_react(self):
        self.auth()
        data = self.client.get(self.url, {'page_size': 1}).data
        self.assertTrue({'count', 'next', 'previous', 'results'} <= set(data))
        self.assertEqual(len(data['results']), 1)

    def test_sin_coincidencias_devuelve_pagina_vacia(self):
        self.auth()
        data = self.client.get(self.url, {'curso': 999999}).data
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['results'], [])

    def test_unidad_heredada_sin_colegio_se_rechaza(self):
        self.auth(self.admin_heredado)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_consulta_no_genera_auditoria(self):
        antes = EventoAuditoria.objects.count()
        self.auth()
        self.client.get(self.url)
        self.assertEqual(EventoAuditoria.objects.count(), antes)

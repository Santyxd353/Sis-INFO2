from datetime import date

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.test import APITestCase

from aplicaciones.calendario.models import CalendarioAcademico
from aplicaciones.institucion.models import Aula, Colegio, Modulo, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import (
    Accion, Admin, EventoAuditoria, ModeloPermitido, PermisoPuesto, Puesto, Rol,
    Usuario,
)

from .models import (
    AsignacionDocente, BloqueHorario, Curso, Grado, HorarioClase, Materia,
    MateriaCurso, Paralelo,
)


class AsignacionDocenteHU11Tests(APITestCase):
    url = '/api/academico/asignaciones-docentes/'
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio_a = Colegio.objects.create(nombre='Colegio A HU11', direccion='A', telefono='1')
        cls.colegio_b = Colegio.objects.create(nombre='Colegio B HU11', direccion='B', telefono='2')
        cls.ua = cls._unidad('HU11-UA', cls.colegio_a)
        cls.ua2 = cls._unidad('HU11-UA2', cls.colegio_a)
        cls.ub = cls._unidad('HU11-UB', cls.colegio_b)
        cls.curso_a, cls.mc_a = cls._curso_y_materia(cls.ua, 'A')
        cls.curso_a2, cls.mc_a2 = cls._curso_y_materia(cls.ua2, 'B')
        cls.curso_b, cls.mc_b = cls._curso_y_materia(cls.ub, 'C')
        cls.gestion_a = cls._gestion(cls.ua, 2026)
        cls.gestion_a_2 = cls._gestion(cls.ua, 2027)
        cls.gestion_a2 = cls._gestion(cls.ua2, 2026)
        cls.gestion_b = cls._gestion(cls.ub, 2026)
        cls.superusuario = Usuario.objects.create_superuser(
            ci='HU11-SUP', email='hu11-sup@example.com', nombre='Super', apellido='HU11',
            username='hu11_sup', fecha_nacimiento='1990-01-01', password=cls.password,
        )
        rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        rol_tutor, _ = Rol.objects.get_or_create(nombre='Tutor')
        cls.prof_a = cls._profesor('PA', cls.ua, rol_profesor)
        cls.prof_a_otro = cls._profesor('PAO', cls.ua, rol_profesor)
        cls.prof_a2 = cls._profesor('PA2', cls.ua2, rol_profesor)
        cls.prof_b = cls._profesor('PB', cls.ub, rol_profesor)
        cls.director = cls._admin('DIR', cls.ua, rol_admin, 'Director')
        cls.admin_colegio = cls._admin('ADM', cls.ua, rol_admin, 'Administrador institucional')
        cls.sin_permiso = cls._usuario('TUT', cls.ua, rol_tutor)
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='asignacion-docente')
        for accion_nombre in ('listar', 'crear', 'editar'):
            accion, _ = Accion.objects.get_or_create(nombre=accion_nombre)
            for usuario in (cls.director, cls.admin_colegio):
                PermisoPuesto.objects.get_or_create(
                    puesto=usuario.admin.puesto, modelo=modelo, accion=accion,
                )

    @classmethod
    def _unidad(cls, codigo, colegio):
        return UnidadEducativa.objects.create(
            codigo_sie=codigo, turno='TARDE', nombre=codigo, colegio=colegio,
        )

    @classmethod
    def _curso_y_materia(cls, unidad, sufijo):
        grado = Grado.objects.create(unidad_educativa=unidad, nivel_educativo='PRI', numero=1)
        paralelo = Paralelo.objects.create(grado=grado, letra=sufijo)
        curso = Curso.objects.create(paralelo=paralelo, nombre=f'Curso {sufijo}')
        materia = Materia.objects.create(nombre=f'Materia HU11 {sufijo}')
        return curso, MateriaCurso.objects.create(curso=curso, materia=materia)

    @classmethod
    def _gestion(cls, unidad, anio):
        return CalendarioAcademico.objects.create(
            unidad_educativa=unidad, año=anio, fecha_inicio=date(anio, 2, 1),
            fecha_fin=date(anio, 11, 30), activo=True,
        )

    @classmethod
    def _usuario(cls, sufijo, unidad, rol):
        return Usuario.objects.create_user(
            ci=f'HU11-{sufijo}', email=f'hu11-{sufijo.lower()}@example.com',
            nombre=sufijo, apellido='HU11', username=f'hu11_{sufijo.lower()}',
            fecha_nacimiento='1990-01-01', password=cls.password, rol=rol, unidad=unidad,
        )

    @classmethod
    def _profesor(cls, sufijo, unidad, rol):
        return Profesor.objects.create(usuario=cls._usuario(sufijo, unidad, rol), unidad=unidad)

    @classmethod
    def _admin(cls, sufijo, unidad, rol, puesto):
        usuario = cls._usuario(sufijo, unidad, rol)
        cargo, _ = Puesto.objects.get_or_create(nombre=puesto)
        Admin.objects.create(usuario=usuario, unidad=unidad, colegio=unidad.colegio, puesto=cargo)
        return usuario

    def payload(self, **cambios):
        data = {
            'tipo': 'MATERIA', 'calendario_academico': self.gestion_a.pk,
            'curso': self.curso_a.pk, 'materia_curso': self.mc_a.pk,
            'profesor': self.prof_a.pk, 'fecha_inicio': '2026-02-10',
            'horas_semanales': 4,
        }
        data.update(cambios)
        return data

    def crear(self, **cambios):
        return AsignacionDocente.objects.create(
            tipo=cambios.get('tipo', 'MATERIA'),
            calendario_academico=cambios.get('calendario', self.gestion_a),
            curso=cambios.get('curso', self.curso_a),
            materia_curso=cambios.get('materia_curso', self.mc_a),
            profesor=cambios.get('profesor', self.prof_a),
            fecha_inicio=cambios.get('fecha_inicio', date(2026, 2, 10)),
        )

    def autenticar(self, usuario=None):
        self.client.force_authenticate(usuario or self.superusuario)

    def test_calendario_es_obligatorio_en_creacion(self):
        self.autenticar()
        response = self.client.post(self.url, self.payload(calendario_academico=None), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('calendario_academico', response.data)

    def test_creacion_materia_valida_y_audita_ambito(self):
        self.autenticar()
        response = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        evento = EventoAuditoria.objects.get(entidad='ASIGNACION_DOCENTE', accion='CREAR')
        self.assertEqual(evento.unidad_educativa, self.ua)
        self.assertEqual(evento.colegio, self.colegio_a)

    def test_creacion_tutor_valida(self):
        self.autenticar()
        response = self.client.post(self.url, self.payload(
            tipo='TUTOR_CURSO', materia_curso=None,
        ), format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_materia_obligatoria_para_tipo_materia(self):
        self.autenticar()
        response = self.client.post(self.url, self.payload(materia_curso=None), format='json')
        self.assertEqual(response.status_code, 400)

    def test_materia_prohibida_para_tutor(self):
        self.autenticar()
        response = self.client.post(self.url, self.payload(tipo='TUTOR_CURSO'), format='json')
        self.assertEqual(response.status_code, 400)

    def test_calendario_y_curso_de_distintas_unidades(self):
        self.autenticar()
        response = self.client.post(self.url, self.payload(calendario_academico=self.gestion_b.pk), format='json')
        self.assertEqual(response.status_code, 400)

    def test_profesor_y_curso_de_distintas_unidades(self):
        self.autenticar()
        response = self.client.post(self.url, self.payload(profesor=self.prof_b.pk), format='json')
        self.assertEqual(response.status_code, 400)

    def test_materia_curso_no_corresponde_al_curso(self):
        self.autenticar()
        response = self.client.post(self.url, self.payload(materia_curso=self.mc_b.pk), format='json')
        self.assertEqual(response.status_code, 400)

    def test_entidad_inactiva_es_rechazada(self):
        self.prof_a.estado = False
        self.prof_a.save(update_fields=['estado'])
        self.autenticar()
        response = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 400)

    def test_fecha_final_anterior_es_rechazada(self):
        self.autenticar()
        response = self.client.post(self.url, self.payload(fecha_fin='2026-02-01'), format='json')
        self.assertEqual(response.status_code, 400)

    def test_duplicidad_activa_en_misma_gestion(self):
        self.crear()
        self.autenticar()
        response = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 400)

    def test_misma_asignacion_permitida_en_otra_gestion(self):
        self.crear()
        self.autenticar()
        response = self.client.post(self.url, self.payload(
            calendario_academico=self.gestion_a_2.pk, fecha_inicio='2027-02-10',
        ), format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_segundo_tutor_misma_gestion_rechazado(self):
        self.crear(tipo='TUTOR_CURSO', materia_curso=None)
        self.autenticar()
        response = self.client.post(self.url, self.payload(
            tipo='TUTOR_CURSO', materia_curso=None, profesor=self.prof_a_otro.pk,
        ), format='json')
        self.assertEqual(response.status_code, 400)

    def test_tutor_mismo_curso_otra_gestion_permitido(self):
        self.crear(tipo='TUTOR_CURSO', materia_curso=None)
        self.autenticar()
        response = self.client.post(self.url, self.payload(
            tipo='TUTOR_CURSO', materia_curso=None,
            calendario_academico=self.gestion_a_2.pk, fecha_inicio='2027-02-10',
        ), format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_no_autenticado_recibe_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_autenticado_sin_permiso_recibe_403(self):
        self.autenticar(self.sin_permiso)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_director_accede_unidad_hermana_y_parametros_no_amplian_colegio(self):
        propio = self.crear()
        self.crear(calendario=self.gestion_a2, curso=self.curso_a2, materia_curso=self.mc_a2, profesor=self.prof_a2)
        self.autenticar(self.director)
        response = self.client.get(self.url, {'unidad_educativa': self.ua2.pk})
        self.assertEqual(response.data['count'], 1)
        detalle = self.client.get(f'{self.url}{propio.pk}/')
        self.assertEqual(detalle.status_code, 200)

    def test_admin_no_director_limitado_a_su_unidad(self):
        self.crear()
        self.crear(calendario=self.gestion_a2, curso=self.curso_a2, materia_curso=self.mc_a2, profesor=self.prof_a2)
        ajeno = self.crear(calendario=self.gestion_b, curso=self.curso_b, materia_curso=self.mc_b, profesor=self.prof_b)
        self.autenticar(self.admin_colegio)
        response = self.client.get(self.url)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.client.get(f'{self.url}{ajeno.pk}/').status_code, 404)

    def test_superadministrador_acceso_global(self):
        self.crear()
        self.crear(calendario=self.gestion_b, curso=self.curso_b, materia_curso=self.mc_b, profesor=self.prof_b)
        self.autenticar()
        self.assertEqual(self.client.get(self.url).data['count'], 2)

    def test_profesor_solo_consulta_sus_asignaciones(self):
        propia = self.crear()
        self.crear(profesor=self.prof_a_otro)
        self.autenticar(self.prof_a.usuario)
        response = self.client.get(self.url)
        self.assertEqual([x['id'] for x in response.data['results']], [propia.pk])

    def test_filtros_validos(self):
        asignacion = self.crear()
        self.crear(tipo='TUTOR_CURSO', materia_curso=None, profesor=self.prof_a_otro)
        self.autenticar()
        filtros = {
            'profesor': self.prof_a.pk, 'curso': self.curso_a.pk,
            'materia_curso': self.mc_a.pk, 'materia': self.mc_a.materia_id,
            'gestion': self.gestion_a.pk, 'tipo': 'MATERIA', 'estado': 'ACTIVO',
            'unidad_educativa': self.ua.pk, 'vigente': '2026-03-01',
        }
        response = self.client.get(self.url, filtros)
        self.assertEqual([x['id'] for x in response.data['results']], [asignacion.pk])

    def test_filtros_invalidos_responden_400(self):
        self.autenticar()
        for params in ({'profesor': 'x'}, {'tipo': 'OTRO'}, {'estado': 'OTRO'}, {'vigente': 'ayer'}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(self.url, params).status_code, 400)

    def test_desactivacion_logica_y_auditoria(self):
        asignacion = self.crear()
        self.autenticar()
        response = self.client.post(f'{self.url}{asignacion.pk}/desactivar/')
        self.assertEqual(response.status_code, 200, response.data)
        asignacion.refresh_from_db()
        self.assertEqual(asignacion.estado, 'INACTIVO')
        self.assertIsNotNone(asignacion.eliminado_at)
        self.assertTrue(EventoAuditoria.objects.filter(
            entidad='ASIGNACION_DOCENTE', accion='DESACTIVAR', entidad_id=str(asignacion.pk),
        ).exists())

    def test_delete_fisico_bloqueado(self):
        asignacion = self.crear()
        self.autenticar()
        self.assertEqual(self.client.delete(f'{self.url}{asignacion.pk}/').status_code, 405)
        self.assertTrue(AsignacionDocente.objects.filter(pk=asignacion.pk).exists())

    def test_dependencia_bloquea_cambio_pero_permite_desactivar(self):
        asignacion = self.crear()
        modulo = Modulo.objects.create(nombre='Módulo HU11', cantidad_aulas=1, colegio_fk=self.colegio_a)
        aula = Aula.objects.create(modulo=modulo, nombre='Aula HU11', capacidad=20)
        bloque = BloqueHorario.objects.create(
            unidad_educativa=self.ua, turno='TARDE', dia=1, orden=1,
            hora_inicio='08:00', hora_fin='09:00',
        )
        HorarioClase.objects.create(
            asignacion_docente=asignacion, profesor=self.prof_a, curso=self.curso_a,
            aula=aula, bloque_horario=bloque, fecha_inicio=date(2026, 2, 10),
        )
        self.autenticar()
        cambio = self.client.patch(f'{self.url}{asignacion.pk}/', {
            'profesor': self.prof_a_otro.pk,
        }, format='json')
        self.assertEqual(cambio.status_code, 400)
        self.assertEqual(self.client.post(f'{self.url}{asignacion.pk}/desactivar/').status_code, 200)

    def test_actualizacion_segura_genera_auditoria(self):
        asignacion = self.crear()
        self.autenticar()
        response = self.client.patch(f'{self.url}{asignacion.pk}/', {
            'horas_semanales': 6,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(EventoAuditoria.objects.filter(
            entidad='ASIGNACION_DOCENTE', accion='ACTUALIZAR', entidad_id=str(asignacion.pk),
        ).exists())

    def test_historico_nullable_puede_leerse(self):
        historico = AsignacionDocente.objects.create(
            tipo='MATERIA', calendario_academico=None, curso=self.curso_a,
            materia_curso=self.mc_a, profesor=self.prof_a, fecha_inicio=date(2025, 2, 1),
            estado='INACTIVO',
        )
        self.autenticar()
        response = self.client.get(f'{self.url}{historico.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['calendario_academico'])

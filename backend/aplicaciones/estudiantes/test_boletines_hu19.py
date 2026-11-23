from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db.models.signals import post_save
from rest_framework.test import APITestCase

from aplicaciones.academico.models import (
    AsignacionDocente, ActividadEvaluacion, Calificacion, Curso, DimensionEvaluacion,
    Grado, Materia, MateriaCurso, Paralelo,
)
from aplicaciones.academico.resultados import calcular_resultado_trimestral
from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import Accion, Admin, EventoAuditoria, ModeloPermitido, PermisoPuesto, PermisoRol, Puesto, Rol, Usuario

from . import boletines
from .models import DocumentoAcademicoEmitido, Estudiante, HistorialInscripcion, Tutor, TutorEstudiante


class BoletinesHU19Tests(APITestCase):
    url = '/api/estudiantes/documentos-academicos/'
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio = Colegio.objects.create(nombre='Colegio HU19', direccion='A', telefono='1')
        cls.unidad = UnidadEducativa.objects.create(
            codigo_sie='HU19-UA', turno='TARDE', nombre='HU19-UA', colegio=cls.colegio,
        )
        cls.otra_unidad = UnidadEducativa.objects.create(
            codigo_sie='HU19-UB', turno='TARDE', nombre='HU19-UB',
            colegio=Colegio.objects.create(nombre='Colegio HU19-B', direccion='B', telefono='2'),
        )
        cls.grado = Grado.objects.create(unidad_educativa=cls.unidad, nivel_educativo='PRI', numero=4)
        cls.paralelo = Paralelo.objects.create(grado=cls.grado, letra='A')
        cls.curso = Curso.objects.create(paralelo=cls.paralelo, nombre='4to A')
        cls.materia = Materia.objects.create(nombre='Matemática HU19')
        cls.materia_curso = MateriaCurso.objects.create(curso=cls.curso, materia=cls.materia)

        cls.gestion = CalendarioAcademico.objects.create(
            unidad_educativa=cls.unidad, año=2026, fecha_inicio=date(2026, 2, 1),
            fecha_fin=date(2026, 11, 30), activo=True,
        )
        cls.otra_gestion = CalendarioAcademico.objects.create(
            unidad_educativa=cls.otra_unidad, año=2026, fecha_inicio=date(2026, 2, 1),
            fecha_fin=date(2026, 11, 30), activo=True,
        )
        cls.periodo = Periodo.objects.create(
            calendario=cls.gestion, tipo_division='TRI', nombre='Trimestre 1',
            fecha_inicio=date(2026, 2, 1), fecha_fin=date(2026, 5, 31), estado='CUR',
        )
        cls.dim_saber = DimensionEvaluacion.objects.get(
            configuracion__calendario_academico=cls.gestion, configuracion__nivel='PRI', codigo='SABER',
        )

        rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        rol_estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante')

        cls.superusuario = Usuario.objects.create_superuser(
            ci='HU19-SUP', email='hu19-sup@example.com', nombre='Super', apellido='HU19',
            username='hu19_sup', fecha_nacimiento='1990-01-01', password=cls.password,
        )
        profesor_usuario = Usuario.objects.create_user(
            ci='HU19-PRF', email='hu19-prf@example.com', nombre='Prof', apellido='HU19',
            username='hu19_prf', fecha_nacimiento='1985-01-01', password=cls.password,
            rol=rol_profesor, unidad=cls.unidad,
        )
        cls.profesor = Profesor.objects.create(usuario=profesor_usuario, unidad=cls.unidad)
        cls.profesor_usuario = profesor_usuario

        admin_usuario = Usuario.objects.create_user(
            ci='HU19-SEC', email='hu19-sec@example.com', nombre='Sec', apellido='HU19',
            username='hu19_sec', fecha_nacimiento='1980-01-01', password=cls.password,
            rol=rol_admin, unidad=cls.unidad,
        )
        puesto, _ = Puesto.objects.get_or_create(nombre='Secretaria')
        Admin.objects.create(usuario=admin_usuario, unidad=cls.unidad, colegio=cls.colegio, puesto=puesto)
        recurso, _ = ModeloPermitido.objects.get_or_create(nombre='documento-academico')
        for nombre in ('listar', 'generar', 'descargar'):
            accion, _ = Accion.objects.get_or_create(nombre=nombre)
            PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=recurso, accion=accion)
        cls.secretaria = admin_usuario

        estudiante_usuario = Usuario.objects.create_user(
            ci='HU19-EST', email='hu19-est@example.com', nombre='Est', apellido='HU19',
            username='hu19_est', fecha_nacimiento='2014-01-01', password=cls.password,
            rol=rol_estudiante, unidad=cls.unidad,
        )
        cls.estudiante = Estudiante.objects.create(
            usuario=estudiante_usuario, rude='HU19-RUDE-1', curso=cls.curso, unidad=cls.unidad,
        )
        cls.historial = HistorialInscripcion.objects.create(
            estudiante=cls.estudiante, curso_nuevo=cls.curso, unidad=cls.unidad, tipo_movimiento='NUEVA',
        )

        asignacion = AsignacionDocente.objects.create(
            tipo='MATERIA', calendario_academico=cls.gestion, curso=cls.curso,
            materia_curso=cls.materia_curso, profesor=cls.profesor, fecha_inicio=date(2026, 2, 10),
        )
        actividad = ActividadEvaluacion.objects.create(
            asignacion_docente=asignacion, periodo=cls.periodo, dimension=cls.dim_saber,
            nombre='Examen HU19', fecha=date(2026, 3, 1), puntaje_maximo=Decimal('100'),
        )
        Calificacion.objects.create(
            actividad=actividad, historial_inscripcion=cls.historial, valor=Decimal('90'),
        )
        cls.resultado = calcular_resultado_trimestral(cls.historial, cls.materia, cls.periodo)

    def autenticar(self, usuario=None):
        self.client.force_authenticate(usuario or self.superusuario)

    # --- Generación de boletín ---

    def test_generar_boletin_notifica_al_estudiante_y_a_su_tutor(self):
        tutor_usuario = Usuario.objects.create_user(
            ci='HU19-TUTN', email='hu19-tutn@example.com', nombre='TutN', apellido='HU19',
            username='hu19_tutn', fecha_nacimiento='1980-01-01', password=self.password,
            rol=Rol.objects.get_or_create(nombre='Tutor')[0], unidad=self.unidad,
        )
        tutor = Tutor.objects.create(usuario=tutor_usuario, parentesco='MAD')
        TutorEstudiante.objects.create(tutor=tutor, estudiante=self.estudiante, es_principal=True)

        self.autenticar(self.secretaria)
        from aplicaciones.comunicacion.models import Aviso
        from aplicaciones.usuarios.models import DispositivoNotificacion
        DispositivoNotificacion.objects.create(usuario=self.estudiante.usuario,
            token='ExponentPushToken[boletin-hu19]', plataforma='ANDROID')
        with patch('aplicaciones.usuarios.notificaciones.requests.post') as notificar:
            response = self.client.post(f'{self.url}generar-boletin/', {
                'historial_inscripcion': self.historial.pk, 'calendario_academico': self.gestion.pk,
                'periodo': self.periodo.pk,
            }, format='json')
        self.assertEqual(response.status_code, 201)
        notificar.assert_not_called()  # TestCase no confirma el commit exterior.
        destinatarios = Aviso.objects.filter(tipo='BOLETIN', datos__documento_academico=response.data['id']).values_list('usuario_id', flat=True)
        self.assertEqual(set(destinatarios), {self.estudiante.usuario_id, tutor_usuario.pk})

    def test_generar_boletin_trimestral_crea_documento_y_pdf(self):
        self.autenticar(self.secretaria)
        response = self.client.post(f'{self.url}generar-boletin/', {
            'historial_inscripcion': self.historial.pk, 'calendario_academico': self.gestion.pk,
            'periodo': self.periodo.pk,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        documento = DocumentoAcademicoEmitido.objects.get(pk=response.data['id'])
        self.assertEqual(documento.tipo, DocumentoAcademicoEmitido.Tipo.BOLETIN)
        self.assertEqual(documento.version, 1)
        self.assertEqual(documento.archivo_mime, 'application/pdf')
        self.assertGreater(documento.archivo_tamano, 0)
        self.assertTrue(
            EventoAuditoria.objects.filter(entidad='DOCUMENTO_ACADEMICO').exists(),
        )

    def test_generar_boletin_dos_veces_incrementa_version(self):
        self.autenticar(self.secretaria)
        payload = {
            'historial_inscripcion': self.historial.pk, 'calendario_academico': self.gestion.pk,
            'periodo': self.periodo.pk,
        }
        primera = self.client.post(f'{self.url}generar-boletin/', payload, format='json')
        self.assertEqual(primera.status_code, 201)
        self.assertIn('version', primera.data)
        self.assertEqual(primera.data['version'], 1)
        segunda = self.client.post(f'{self.url}generar-boletin/', payload, format='json')
        self.assertEqual(segunda.status_code, 201)
        self.assertIn('version', segunda.data)
        self.assertEqual(segunda.data['version'], 2)

    def test_generar_boletin_anual_sin_periodo(self):
        self.autenticar(self.secretaria)
        response = self.client.post(f'{self.url}generar-boletin/', {
            'historial_inscripcion': self.historial.pk, 'calendario_academico': self.gestion.pk,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data['periodo'])

    def test_generar_boletin_sin_configuracion_evaluacion_devuelve_error_de_dominio(self):
        from aplicaciones.academico.signals import crear_configuracion_evaluacion_default

        post_save.disconnect(crear_configuracion_evaluacion_default, sender=CalendarioAcademico)
        try:
            gestion = CalendarioAcademico.objects.create(
                unidad_educativa=self.unidad, año=2025, fecha_inicio=date(2025, 2, 1),
                fecha_fin=date(2025, 11, 30), activo=False,
            )
        finally:
            post_save.connect(crear_configuracion_evaluacion_default, sender=CalendarioAcademico)
        periodo = Periodo.objects.create(
            calendario=gestion, tipo_division='TRI', nombre='Trimestre aislado',
            fecha_inicio=date(2025, 2, 1), fecha_fin=date(2025, 5, 31), estado='CUR',
        )
        self.autenticar(self.secretaria)
        documentos_antes = DocumentoAcademicoEmitido.objects.count()
        auditoria_antes = EventoAuditoria.objects.filter(entidad='DOCUMENTO_ACADEMICO').count()
        with patch('aplicaciones.estudiantes.boletines.default_storage.save') as guardar_archivo:
            response = self.client.post(f'{self.url}generar-boletin/', {
                'historial_inscripcion': self.historial.pk, 'calendario_academico': gestion.pk,
                'periodo': periodo.pk,
            }, format='json')
        guardar_archivo.assert_not_called()

        self.assertEqual(response.status_code, 400)
        self.assertIn('calendario_academico', response.data)
        self.assertIn('No existe una configuraci', str(response.data['calendario_academico']))
        self.assertNotIn('Traceback', response.content.decode())
        self.assertEqual(DocumentoAcademicoEmitido.objects.count(), documentos_antes)
        self.assertEqual(EventoAuditoria.objects.filter(entidad='DOCUMENTO_ACADEMICO').count(), auditoria_antes)

    def test_periodo_de_otra_gestion_es_rechazado(self):
        otro_periodo = Periodo.objects.create(
            calendario=self.otra_gestion, tipo_division='TRI', nombre='Otro trimestre',
            fecha_inicio=date(2026, 2, 1), fecha_fin=date(2026, 5, 31), estado='CUR',
        )
        self.autenticar(self.secretaria)
        response = self.client.post(f'{self.url}generar-boletin/', {
            'historial_inscripcion': self.historial.pk, 'calendario_academico': self.gestion.pk,
            'periodo': otro_periodo.pk,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('periodo', response.data)

    def test_secretaria_no_puede_generar_boletin_de_otra_unidad(self):
        otro_estudiante_usuario = Usuario.objects.create_user(
            ci='HU19-EST2', email='hu19-est2@example.com', nombre='Est2', apellido='HU19',
            username='hu19_est2', fecha_nacimiento='2014-01-01', password=self.password,
            rol=Rol.objects.get(nombre='Estudiante'), unidad=self.otra_unidad,
        )
        grado_b = Grado.objects.create(unidad_educativa=self.otra_unidad, nivel_educativo='PRI', numero=4)
        paralelo_b = Paralelo.objects.create(grado=grado_b, letra='A')
        curso_b = Curso.objects.create(paralelo=paralelo_b, nombre='4to A - B')
        estudiante_b = Estudiante.objects.create(
            usuario=otro_estudiante_usuario, rude='HU19-RUDE-2', curso=curso_b, unidad=self.otra_unidad,
        )
        historial_b = HistorialInscripcion.objects.create(
            estudiante=estudiante_b, curso_nuevo=curso_b, unidad=self.otra_unidad, tipo_movimiento='NUEVA',
        )
        self.autenticar(self.secretaria)
        response = self.client.post(f'{self.url}generar-boletin/', {
            'historial_inscripcion': historial_b.pk, 'calendario_academico': self.otra_gestion.pk,
        }, format='json')
        self.assertEqual(response.status_code, 403)

    # --- Generación de centralizador ---

    def test_generar_centralizador_incluye_resultado_del_curso(self):
        self.autenticar(self.secretaria)
        response = self.client.post(f'{self.url}generar-centralizador/', {
            'curso': self.curso.pk, 'calendario_academico': self.gestion.pk, 'periodo': self.periodo.pk,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        documento = DocumentoAcademicoEmitido.objects.get(pk=response.data['id'])
        self.assertEqual(documento.tipo, DocumentoAcademicoEmitido.Tipo.CENTRALIZADOR)
        self.assertIsNone(documento.historial_inscripcion)
        self.assertEqual(documento.curso_id, self.curso.pk)

    # --- Permisos y descarga ---

    def test_profesor_no_puede_generar_boletines(self):
        self.autenticar(self.profesor_usuario)
        response = self.client.post(f'{self.url}generar-boletin/', {
            'historial_inscripcion': self.historial.pk, 'calendario_academico': self.gestion.pk,
        }, format='json')
        self.assertEqual(response.status_code, 403)

    def test_anonimo_no_puede_listar(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_secretaria_sin_permiso_no_puede_listar(self):
        PermisoPuesto.objects.filter(puesto=self.secretaria.admin.puesto, modelo__nombre='documento-academico', accion__nombre='listar').delete()
        self.autenticar(self.secretaria)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_permisos_son_especificos_por_accion(self):
        PermisoPuesto.objects.filter(puesto=self.secretaria.admin.puesto, modelo__nombre='documento-academico', accion__nombre='generar').delete()
        self.autenticar(self.secretaria)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(f'{self.url}generar-boletin/', {}, format='json').status_code, 403)

    def test_superadmin_requiere_permiso_y_contexto_explicitos(self):
        self.autenticar(self.superusuario)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        recurso = ModeloPermitido.objects.get(nombre='documento-academico')
        accion = Accion.objects.get(nombre='listar')
        PermisoRol.objects.get_or_create(rol=self.superusuario.rol, modelo=recurso, accion=accion)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(self.url, HTTP_X_COLEGIO_ID=str(self.colegio.pk)).status_code, 200)

    def test_descargar_devuelve_pdf(self):
        documento, _ = boletines.emitir_boletin(
            self.historial, self.gestion, periodo=self.periodo, usuario=self.secretaria,
        )
        self.autenticar(self.secretaria)
        response = self.client.get(f'{self.url}{documento.pk}/descargar/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_listar_por_curso_incluye_boletin_individual(self):
        documento, _ = boletines.emitir_boletin(
            self.historial, self.gestion, periodo=self.periodo, usuario=self.secretaria,
        )
        self.autenticar(self.secretaria)
        response = self.client.get(self.url, {'curso': self.curso.pk})
        self.assertEqual(response.status_code, 200)
        filas = response.data.get('results', []) if isinstance(response.data, dict) else response.data
        self.assertIn(documento.pk, [fila['id'] for fila in filas])

    def test_secretaria_de_otra_unidad_no_ve_el_documento(self):
        documento, _ = boletines.emitir_boletin(
            self.historial, self.gestion, periodo=self.periodo, usuario=self.secretaria,
        )
        secretaria_b_usuario = Usuario.objects.create_user(
            ci='HU19-SECB', email='hu19-secb@example.com', nombre='SecB', apellido='HU19',
            username='hu19_secb', fecha_nacimiento='1980-01-01', password=self.password,
            rol=Rol.objects.get(nombre='Admin'), unidad=self.otra_unidad,
        )
        Admin.objects.create(
            usuario=secretaria_b_usuario, unidad=self.otra_unidad,
            colegio=self.otra_unidad.colegio,
            puesto=Puesto.objects.get(nombre='Secretaria'),
        )
        self.autenticar(secretaria_b_usuario)
        response = self.client.get(f'{self.url}{documento.pk}/')
        self.assertEqual(response.status_code, 404)

    # --- Autoservicio: tutor/estudiante ven solo sus propios boletines ---

    def test_estudiante_puede_listar_y_descargar_su_propio_boletin(self):
        documento, _ = boletines.emitir_boletin(
            self.historial, self.gestion, periodo=self.periodo, usuario=self.secretaria,
        )
        self.autenticar(self.estudiante.usuario)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        filas = respuesta.data.get('results', []) if isinstance(respuesta.data, dict) else respuesta.data
        self.assertEqual([fila['id'] for fila in filas], [documento.pk])
        descarga = self.client.get(f'{self.url}{documento.pk}/descargar/')
        self.assertEqual(descarga.status_code, 200)

    def test_estudiante_no_ve_el_centralizador_de_su_curso(self):
        boletines.emitir_centralizador(
            self.curso, self.gestion, periodo=self.periodo, usuario=self.secretaria,
        )
        self.autenticar(self.estudiante.usuario)
        respuesta = self.client.get(self.url)
        filas = respuesta.data.get('results', []) if isinstance(respuesta.data, dict) else respuesta.data
        self.assertEqual(filas, [])

    def test_tutor_puede_ver_el_boletin_de_su_hijo_pero_no_de_otro_estudiante(self):
        documento, _ = boletines.emitir_boletin(
            self.historial, self.gestion, periodo=self.periodo, usuario=self.secretaria,
        )
        otro_usuario = Usuario.objects.create_user(
            ci='HU19-EST3', email='hu19-est3@example.com', nombre='Est3', apellido='HU19',
            username='hu19_est3', fecha_nacimiento='2014-01-01', password=self.password,
            rol=Rol.objects.get(nombre='Estudiante'), unidad=self.unidad,
        )
        otro_estudiante = Estudiante.objects.create(
            usuario=otro_usuario, rude='HU19-RUDE-3', curso=self.curso, unidad=self.unidad,
        )
        otro_historial = HistorialInscripcion.objects.create(
            estudiante=otro_estudiante, curso_nuevo=self.curso, unidad=self.unidad, tipo_movimiento='NUEVA',
        )
        boletines.emitir_boletin(otro_historial, self.gestion, periodo=self.periodo, usuario=self.secretaria)

        tutor_usuario = Usuario.objects.create_user(
            ci='HU19-TUT', email='hu19-tut@example.com', nombre='Tut', apellido='HU19',
            username='hu19_tut', fecha_nacimiento='1980-01-01', password=self.password,
            rol=Rol.objects.get_or_create(nombre='Tutor')[0], unidad=self.unidad,
        )
        tutor = Tutor.objects.create(usuario=tutor_usuario, parentesco='PAD')
        TutorEstudiante.objects.create(tutor=tutor, estudiante=self.estudiante, es_principal=True)

        self.autenticar(tutor_usuario)
        respuesta = self.client.get(self.url)
        filas = respuesta.data.get('results', []) if isinstance(respuesta.data, dict) else respuesta.data
        self.assertEqual([fila['id'] for fila in filas], [documento.pk])

    # --- Servicio de generación (sin pasar por la API) ---

    def test_emitir_boletin_genera_pdf_valido(self):
        documento, ruta = boletines.emitir_boletin(self.historial, self.gestion, periodo=self.periodo)
        from django.core.files.storage import default_storage
        with default_storage.open(ruta, 'rb') as archivo:
            contenido = archivo.read()
        self.assertTrue(contenido.startswith(b'%PDF'))
        self.assertEqual(documento.archivo_tamano, len(contenido))

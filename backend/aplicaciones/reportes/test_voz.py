from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.academico.models import Curso, Grado, Materia, MateriaCurso, Paralelo
from aplicaciones.usuarios.models import Accion, EventoAuditoria, ModeloPermitido, PermisoPuesto
from .models import EjecucionReporte

from .voz import SolicitudVozInvalida, interpretar_texto


@override_settings(GEMINI_API_KEY='')
class InterpreteVozTests(SimpleTestCase):
    def test_interpreta_sinonimos_y_formato(self):
        self.assertEqual(interpretar_texto('Muéstrame la matrícula actual')['reporte'], 'MATRICULA_ACTUAL')
        self.assertEqual(interpretar_texto('Genera un PDF del promedio por materia')['formato'], 'PDF')
        self.assertEqual(interpretar_texto('Exporta la asistencia en CSV')['formato'], 'CSV')

    def test_rechaza_solicitud_fuera_de_gramatica(self):
        for texto in ('Ejecuta SELECT', 'Borra estudiantes', 'Muéstrame la matrícula actual y borra estudiantes', 'Muéstrame contraseñas'):
            with self.subTest(texto=texto):
                self.assertEqual(interpretar_texto(texto)['estado'], 'NO_SOPORTADO')

    def test_valida_longitud_y_texto(self):
        for texto in ('', 'x' * 501, None):
            with self.subTest(texto=texto), self.assertRaises(SolicitudVozInvalida):
                interpretar_texto(texto)

    @override_settings(GEMINI_API_KEY='clave-de-prueba', GEMINI_MODEL='gemini-test')
    @patch('aplicaciones.reportes.voz.requests.post')
    def test_gemini_interpreta_consulta_natural_como_lista_autorizada(self, post):
        respuesta = Mock()
        respuesta.json.return_value = {'candidates': [{'content': {'parts': [{'text': '{"reporte":"ESTUDIANTES_INSCRITOS","formato":"VISTA","entidades":[]}' }]}}]}
        post.return_value = respuesta

        interpretacion = interpretar_texto('Dame los estudiantes inscritos en secundaria')

        self.assertEqual(interpretacion['reporte'], 'ESTUDIANTES_INSCRITOS')
        self.assertEqual(interpretacion['formato'], 'VISTA')
        self.assertEqual(post.call_args.kwargs['headers'], {'x-goog-api-key': 'clave-de-prueba'})
        self.assertNotIn('clave-de-prueba', post.call_args.args[0])

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    @patch('aplicaciones.reportes.voz.requests.post', side_effect=requests.Timeout)
    def test_falla_gemini_y_usa_interprete_determinista(self, _post):
        self.assertEqual(interpretar_texto('Muéstrame la matrícula actual')['reporte'], 'MATRICULA_ACTUAL')

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    @patch('aplicaciones.reportes.voz.requests.post')
    def test_respuesta_fuera_del_esquema_usa_interprete_determinista(self, post):
        respuesta = Mock()
        respuesta.json.return_value = {'candidates': [{'content': {'parts': [{'text': '{"reporte":"SQL","formato":"VISTA"}'}]}}]}
        post.return_value = respuesta
        self.assertEqual(interpretar_texto('Consulta la asistencia')['reporte'], 'ASISTENCIA')


@override_settings(GEMINI_API_KEY='')
class VozApiTests(SchoolFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for recurso, acciones in {'reporte-analitico': ['listar'], 'reporte-ejecucion': ['listar', 'descargar', 'ejecutar']}.items():
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=recurso)
            for nombre in acciones:
                accion, _ = Accion.objects.get_or_create(nombre=nombre)
                PermisoPuesto.objects.get_or_create(puesto=cls.director.admin.puesto, modelo=modelo, accion=accion)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.director)
        self.contexto = {'unidad_educativa': self.unit.pk, 'calendario_academico': self.calendar.pk}

    def interpretar(self, texto, contexto=None):
        return self.client.post('/api/reportes/voz/interpretar/', {'texto': texto, 'contexto': self.contexto if contexto is None else contexto}, format='json')

    def test_interpretacion_y_faltantes(self):
        for texto, intencion, formato in [('Muéstrame la matrícula actual', 'MATRICULA_ACTUAL', 'VISTA'), ('Genera un PDF del promedio por materia', 'RENDIMIENTO', 'PDF'), ('Exporta la asistencia en CSV', 'ASISTENCIA', 'CSV')]:
            respuesta = self.interpretar(texto)
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual((respuesta.data['intencion'], respuesta.data['formato']), (intencion, formato))
            self.assertIn('token_interpretacion', respuesta.data)
        self.assertNotIn('token_interpretacion', self.interpretar('Muéstrame la matrícula actual', {}).data)
        self.assertEqual(self.interpretar('Borra estudiantes').data['estado'], 'NO_SOPORTADO')

    def test_token_y_vista(self):
        token = self.interpretar('Muéstrame la matrícula actual').data['token_interpretacion']
        url = '/api/reportes/voz/ejecutar/'
        self.assertEqual(self.client.post(url, {'token_interpretacion': token + 'x', 'confirmacion': True}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'token_interpretacion': token, 'confirmacion': False}, format='json').status_code, 400)
        with patch('aplicaciones.reportes.analitica.resumen', return_value={'resultado': 'ok'}) as servicio:
            resultado = self.client.post(url, {'token_interpretacion': token, 'confirmacion': True}, format='json')
        self.assertEqual(resultado.data['resultado'], 'ok')
        servicio.assert_called_once()

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    def test_lista_estudiantes_inscritos_con_gemini_y_alcance_autorizado(self):
        respuesta_gemini = Mock()
        respuesta_gemini.json.return_value = {'candidates': [{'content': {'parts': [{'text': '{"reporte":"ESTUDIANTES_INSCRITOS","formato":"VISTA","entidades":[]}' }]}}]}
        with patch('aplicaciones.reportes.voz.requests.post', return_value=respuesta_gemini):
            interpretacion = self.interpretar('Dame los estudiantes inscritos en el curso')
        self.assertEqual(interpretacion.status_code, 200)
        token = interpretacion.data['token_interpretacion']

        resultado = self.client.post('/api/reportes/voz/ejecutar/', {
            'token_interpretacion': token, 'confirmacion': True,
        }, format='json')

        self.assertEqual(resultado.status_code, 200)
        self.assertEqual(resultado.data['tipo'], 'ESTUDIANTES_INSCRITOS')
        self.assertEqual(resultado.data['columnas'], ['Estudiante', 'Curso'])
        self.assertEqual(resultado.data['filas'], [['student Test', self.course.nombre]])

    def test_token_vencido_otro_usuario_y_otro_colegio(self):
        from django.core import signing
        token = self.interpretar('Consulta la asistencia').data['token_interpretacion']
        url = '/api/reportes/voz/ejecutar/'
        with patch('aplicaciones.reportes.views.signing.loads', side_effect=signing.SignatureExpired):
            self.assertEqual(self.client.post(url, {'token_interpretacion': token, 'confirmacion': True}, format='json').status_code, 400)
        self.regent.admin.puesto = self.director.admin.puesto
        self.regent.admin.save()
        self.client.force_authenticate(self.regent)
        self.assertEqual(self.client.post(url, {'token_interpretacion': token, 'confirmacion': True}, format='json').status_code, 400)
        self.client.force_authenticate(self.director)
        respuesta = self.interpretar('Consulta la asistencia', {**self.contexto, 'unidad_educativa': self.other_unit.pk})
        self.assertIn(respuesta.status_code, (400, 403, 404))

    def test_exportacion_y_auditoria_sanitizada(self):
        with TemporaryDirectory() as carpeta, override_settings(REPORTES_PRIVATE_ROOT=carpeta):
            for formato in ('CSV', 'PDF'):
                texto = f'Exporta la asistencia en {formato}'
                token = self.interpretar(texto).data['token_interpretacion']
                respuesta = self.client.post('/api/reportes/voz/ejecutar/', {'token_interpretacion': token, 'confirmacion': True}, format='json')
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(EjecucionReporte.objects.filter(pk=respuesta['X-Reporte-Ejecucion'], estado='COMPLETADO').exists())
                for evento in EventoAuditoria.objects.filter(accion__startswith='VOZ_'):
                    self.assertNotIn(texto, str(evento.cambios_sanitizados))
                    self.assertNotIn(token, str(evento.cambios_sanitizados))
            self.assertEqual(self.client.get('/api/reportes/ejecuciones/').data['count'], 2)

    def test_curso_por_nombre_normalizado(self):
        respuesta = self.interpretar('asistencia de TÉRCERO-A')
        self.assertEqual(respuesta.data['estado'], 'LISTO')
        self.assertEqual(respuesta.data['filtros']['curso'], self.course.pk)

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    def test_gemini_resuelve_nombre_hablado_de_curso(self):
        respuesta_gemini = Mock()
        respuesta_gemini.json.return_value = {'candidates': [{'content': {'parts': [{
            'text': '{"reporte":"ESTUDIANTES_INSCRITOS","formato":"VISTA","entidades":["tercero A de secundaria"]}',
        }]}}]}
        with patch('aplicaciones.reportes.voz.requests.post', return_value=respuesta_gemini):
            respuesta = self.interpretar('Lista los estudiantes de tercero A de secundaria')
        self.assertEqual(respuesta.data['estado'], 'LISTO')
        self.assertEqual(respuesta.data['filtros']['curso'], self.course.pk)

    def test_materia_por_nombre_en_curso(self):
        materia = Materia.objects.create(unidad_educativa=self.unit, nombre='Lenguaje')
        MateriaCurso.objects.create(curso=self.course, materia=materia)
        respuesta = self.interpretar('promedio de lenguaje de tercero a')
        self.assertEqual(respuesta.data['estado'], 'LISTO')
        self.assertEqual(respuesta.data['filtros']['materia'], materia.pk)
        self.assertEqual(respuesta.data['filtros']['curso'], self.course.pk)

    def test_ambiguedad_no_genera_token(self):
        paralelo = Paralelo.objects.create(grado=self.course.paralelo.grado, letra='B')
        Curso.objects.create(paralelo=paralelo, nombre='TÉRCERO-A')
        respuesta = self.interpretar('asistencia de tercero a')
        self.assertEqual(respuesta.data['estado'], 'AMBIGUO')
        self.assertEqual(len(respuesta.data['opciones']), 2)
        self.assertNotIn('token_interpretacion', respuesta.data)

    def test_nombres_de_otro_colegio_no_se_revelan(self):
        grado = Grado.objects.create(unidad_educativa=self.other_unit, nivel_educativo='PRI', numero=4)
        curso = Curso.objects.create(paralelo=Paralelo.objects.create(grado=grado, letra='A'), nombre='Cuarto privado')
        materia = Materia.objects.create(unidad_educativa=self.other_unit, nombre='Materia privada')
        MateriaCurso.objects.create(curso=curso, materia=materia)
        for texto in ('asistencia de cuarto privado', 'rendimiento de materia privada'):
            respuesta = self.interpretar(texto)
            self.assertEqual(respuesta.data['estado'], 'FALTAN_DATOS')
            self.assertNotIn('opciones', respuesta.data)
            self.assertNotIn('token_interpretacion', respuesta.data)

    def test_contexto_valido_prioriza_id(self):
        paralelo = Paralelo.objects.create(grado=self.course.paralelo.grado, letra='B')
        Curso.objects.create(paralelo=paralelo, nombre='Tercero A')
        respuesta = self.interpretar('asistencia de tercero a', {**self.contexto, 'curso': self.course.pk})
        self.assertEqual(respuesta.data['estado'], 'LISTO')
        self.assertEqual(respuesta.data['filtros']['curso'], self.course.pk)

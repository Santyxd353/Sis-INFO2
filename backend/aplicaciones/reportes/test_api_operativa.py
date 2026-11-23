from unittest.mock import patch
import csv
import io
from tempfile import TemporaryDirectory
from pathlib import Path

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import Accion, EventoAuditoria, ModeloPermitido, PermisoPuesto, Puesto, Rol, Usuario
from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.institucion.models import UnidadEducativa
from aplicaciones.academico.models import Grado, Paralelo, Curso
from .models import EjecucionReporte, ReporteDefinicion


class ApiOperativaTests(SchoolFixture, TestCase):
    def setUp(self):
        super().setUp()
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        configuracion = override_settings(REPORTES_PRIVATE_ROOT=temporal.name)
        configuracion.enable()
        self.addCleanup(configuracion.disable)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        secretaria, _ = Puesto.objects.get_or_create(nombre='Secretaria')
        cls.regent.admin.puesto = secretaria
        cls.regent.admin.save()
        for puesto in (cls.director.admin.puesto, secretaria):
            for recurso, acciones in {'reporte-definicion': ('listar', 'crear', 'editar', 'archivar'), 'reporte-ejecucion': ('listar', 'ejecutar', 'descargar')}.items():
                modelo, _ = ModeloPermitido.objects.get_or_create(nombre=recurso)
                for nombre in acciones:
                    accion, _ = Accion.objects.get_or_create(nombre=nombre)
                    PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)

    def cliente(self, usuario):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(usuario)))
        return client

    def crear(self, client, **extra):
        data = {'nombre': 'Reporte', 'codigo_fuente': 'ESTUDIANTES_INSCRITOS',
                'especificacion': {'columnas': ['nombre', 'curso'], 'filtros': [], 'orden': []}}
        data.update(extra)
        return client.post('/api/reportes/definiciones/', data, format='json')

    def test_catalogo_y_permisos(self):
        self.assertEqual(APIClient().get('/api/reportes/catalogo/').status_code, 401)
        for user in (self.teacher, self.tutor_user, self.student_user):
            self.assertEqual(self.cliente(user).get('/api/reportes/catalogo/').status_code, 403)
        rol, _ = Rol.objects.get_or_create(nombre='SuperAdmin')
        superuser = Usuario.objects.create_user(ci='supercatalogo', username='supercatalogo', email='supercatalogo@example.com', nombre='Super', apellido='Prueba', rol=rol)
        self.assertEqual(self.cliente(superuser).get('/api/reportes/catalogo/').status_code, 403)
        client = self.cliente(self.director)
        response = client.get('/api/reportes/catalogo/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({x['codigo'] for x in response.data['results']}, {
            'ESTUDIANTES_INSCRITOS', 'ASISTENCIA_RESUMEN', 'RENDIMIENTO_ACADEMICO',
            'INCIDENTES_DISCIPLINARIOS',
        })
        self.assertEqual(client.get('/api/reportes/catalogo/RIESGO_ACADEMICO/').status_code, 404)
        self.assertEqual(client.get('/api/reportes/catalogo/ESTUDIANTES_INSCRITOS/').status_code, 200)
        self.assertEqual(client.post('/api/reportes/catalogo/', {}, format='json').status_code, 405)

    def test_crud_previsualizacion_y_auditoria(self):
        client = self.cliente(self.director)
        result = self.crear(client)
        self.assertEqual(result.status_code, 201, result.data)
        pk = result.data['id']
        self.assertEqual(client.patch(f'/api/reportes/definiciones/{pk}/', {'nombre': 'Otro'}, format='json').status_code, 200)
        self.assertEqual(client.patch(f'/api/reportes/definiciones/{pk}/', {'codigo_fuente': 'RENDIMIENTO_ACADEMICO'}, format='json').status_code, 400)
        self.assertEqual(client.delete(f'/api/reportes/definiciones/{pk}/').status_code, 405)
        preview = client.post('/api/reportes/previsualizar/', {'definicion_id': pk}, format='json')
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['cantidad'], 1)
        self.assertEqual(len(preview.data['filas'][0]), 2)
        ejecucion = EjecucionReporte.objects.get(pk=preview.data['ejecucion_id'])
        self.assertEqual(ejecucion.estado, 'COMPLETADO')
        evento = EventoAuditoria.objects.get(entidad='REPORTE_EJECUCION', entidad_id=str(ejecucion.pk))
        self.assertEqual(evento.correlacion, ejecucion.correlacion)
        self.assertEqual(evento.cambios_sanitizados['cantidad_filas'], 1)
        self.assertNotIn('student', str(evento.cambios_sanitizados))
        self.assertEqual(client.post(f'/api/reportes/definiciones/{pk}/archivar/', {}, format='json').status_code, 200)
        self.assertEqual(client.post('/api/reportes/previsualizar/', {'definicion_id': pk}, format='json').status_code, 404)

    def test_alcance_validaciones_y_rollback(self):
        director = self.cliente(self.director)
        self.assertEqual(self.crear(director, unidad_educativa=self.other_unit.pk).status_code, 400)
        secretaria = self.cliente(self.regent)
        result = self.crear(secretaria)
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(result.data['unidad_educativa'], self.unit.pk)
        self.assertEqual(director.get(f"/api/reportes/definiciones/{result.data['id']}/").status_code, 404)
        self.assertEqual(self.crear(director, especificacion={'sql': 'select *'}).status_code, 400)
        self.assertEqual(self.crear(director, codigo_fuente='RIESGO_ACADEMICO').status_code, 400)
        with patch('aplicaciones.reportes.views.registrar_evento', side_effect=RuntimeError('fallo')):
            with self.assertRaises(RuntimeError):
                self.crear(director, nombre='Reporte con auditoría')
        self.assertFalse(ReporteDefinicion.objects.filter(propietario=self.director, nombre='Reporte con auditoría').exists())

    def test_filtro_orden_error_y_reversion_previsualizacion(self):
        client = self.cliente(self.director)
        spec = {'columnas': ['nombre'], 'filtros': [{'campo': 'curso', 'operador': 'eq', 'valor': self.course.pk}],
                'orden': [{'campo': 'curso', 'direccion': 'desc'}]}
        created = self.crear(client, unidad_educativa=self.unit.pk, especificacion=spec)
        self.assertEqual(created.status_code, 201, created.data)
        pk = created.data['id']
        url = '/api/reportes/previsualizar/'
        result = client.post(url, {'definicion_id': pk}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['cantidad'], 1)
        self.assertEqual(len(result.data['filas'][0]), 1)
        before = EjecucionReporte.objects.count()
        with patch('aplicaciones.reportes.views.registrar_evento', side_effect=RuntimeError('auditoria')):
            with self.assertRaises(RuntimeError):
                client.post(url, {'definicion_id': pk}, format='json')
        self.assertEqual(EjecucionReporte.objects.count(), before)
        with patch('aplicaciones.reportes.views.ejecutar_fuente', side_effect=ValueError('dato privado')):
            result = client.post(url, {'definicion_id': pk}, format='json')
        self.assertEqual(result.status_code, 400)
        self.assertNotIn('dato privado', str(result.data))
        execution = EjecucionReporte.objects.get(pk=result.data['ejecucion_id'])
        self.assertEqual(execution.estado, 'ERROR')
        self.assertIsNotNone(execution.finalizada_at)

    def test_limite_con_datos_reales(self):
        usuarios = Usuario.objects.bulk_create([
            Usuario(ci=f'testlimite{i}', username=f'testlimite{i}', email=f'limite{i}@example.com',
                    nombre='Prueba', apellido=str(i), rol=self.student_user.rol, unidad=self.unit)
            for i in range(101)
        ])
        Estudiante.objects.bulk_create([
            Estudiante(usuario=u, rude=f'R-LIM-{i}', curso=self.course, unidad=self.unit)
            for i, u in enumerate(usuarios)
        ])
        client = self.cliente(self.director)
        created = self.crear(client)
        result = client.post('/api/reportes/previsualizar/', {'definicion_id': created.data['id']}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['cantidad'], 100)
        self.assertTrue(result.data['limite_alcanzado'])
        self.assertEqual(Estudiante.objects.filter(unidad=self.unit).count(), 102)

    def test_director_unidad_no_expone_otra_unidad_del_mismo_colegio(self):
        unidad = UnidadEducativa.objects.create(colegio=self.school, codigo_sie='HU-C', turno='TARDE', nombre='Unidad C')
        grado = Grado.objects.create(unidad_educativa=unidad, nivel_educativo='PRI', numero=3)
        curso = Curso.objects.create(paralelo=Paralelo.objects.create(grado=grado, letra='C'), nombre='Tercero C')
        user = Usuario.objects.create_user(ci='otraunidad', username='otraunidad', email='otraunidad@example.com', nombre='Otra', apellido='Persona', rol=self.student_user.rol, unidad=unidad)
        Estudiante.objects.create(usuario=user, rude='RUDE-OTRA', curso=curso, unidad=unidad)
        client = self.cliente(self.director)
        created = self.crear(client, unidad_educativa=self.unit.pk)
        result = client.post('/api/reportes/previsualizar/', {'definicion_id': created.data['id']}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['cantidad'], 1)
        self.assertNotIn('Otra Persona', str(result.data['filas']))

    def test_restricciones_entrada_y_archivo_idempotente(self):
        client = self.cliente(self.director)
        self.assertEqual(self.crear(client, especificacion={'columnas': ['curso__nombre'], 'filtros': [], 'orden': []}).status_code, 400)
        self.assertEqual(self.crear(client, especificacion={'columnas': ['nombre'], 'filtros': [{'campo': 'estado', 'operador': 'eq', 'valor': 'SELECT *'}], 'orden': []}).status_code, 400)
        first = self.crear(client)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(self.crear(client).status_code, 400)
        pk = first.data['id']
        self.assertEqual(client.put(f'/api/reportes/definiciones/{pk}/', {}, format='json').status_code, 405)
        self.assertEqual(client.post(f'/api/reportes/definiciones/{pk}/archivar/', {}, format='json').status_code, 200)
        self.assertEqual(client.post(f'/api/reportes/definiciones/{pk}/archivar/', {}, format='json').status_code, 200)
        self.assertEqual(client.patch(f'/api/reportes/definiciones/{pk}/', {'nombre': 'Nuevo'}, format='json').status_code, 400)
        self.assertEqual(EventoAuditoria.objects.filter(entidad='REPORTE_DEFINICION', entidad_id=str(pk), accion='ARCHIVAR').count(), 1)
        self.assertEqual(client.post('/api/reportes/previsualizar/', {'columnas': ['nombre']}, format='json').status_code, 400)

    def test_exportaciones_controladas_registran_ejecucion_y_protegen_csv(self):
        client = self.cliente(self.director)
        resultado = self.crear(client, especificacion={
            'columnas': ['nombre', 'curso'], 'filtros': [], 'orden': [],
        })
        self.assertEqual(resultado.status_code, 201, resultado.data)
        for formato, contenido in (('CSV', b'\xef\xbb\xbf'), ('PDF', b'%PDF')):
            with self.subTest(formato=formato):
                respuesta = client.post('/api/reportes/exportar/', {
                    'definicion_id': resultado.data['id'], 'formato': formato,
                }, format='json')
                self.assertEqual(respuesta.status_code, 200, respuesta.content[:200])
                self.assertTrue(respuesta.content.startswith(contenido))
                self.assertIn('attachment;', respuesta['Content-Disposition'])
                ejecucion = EjecucionReporte.objects.get(pk=respuesta['X-Reporte-Ejecucion'])
                self.assertEqual(ejecucion.estado, 'COMPLETADO')
                self.assertEqual(ejecucion.formato, formato)
                self.assertIsNotNone(ejecucion.archivo_checksum)
                self.assertTrue((Path(self.settings_root()) / ejecucion.archivo_referencia).is_file())
                descarga = client.get(f'/api/reportes/ejecuciones/{ejecucion.pk}/descargar/')
                self.assertEqual(descarga.status_code, 200)
                self.assertEqual(descarga.content, respuesta.content)
        salida = list(csv.reader(io.StringIO(client.post('/api/reportes/exportar/', {
            'definicion_id': resultado.data['id'], 'formato': 'CSV',
        }, format='json').content.decode('utf-8-sig'))))
        self.assertEqual(salida[0], ['Nombre', 'Curso'])
        self.assertEqual(client.post('/api/reportes/exportar/', {
            'definicion_id': resultado.data['id'], 'formato': 'XLSX',
        }, format='json').status_code, 400)

    def settings_root(self):
        from django.conf import settings
        return settings.REPORTES_PRIVATE_ROOT

    def test_historial_archivado_y_aislamiento(self):
        client = self.cliente(self.director)
        definicion = self.crear(client).data
        respuesta = client.post('/api/reportes/exportar/', {'definicion_id': definicion['id'], 'formato': 'CSV'}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        pk = respuesta['X-Reporte-Ejecucion']
        lista = client.get('/api/reportes/ejecuciones/', {'formato': 'CSV'})
        self.assertEqual(lista.status_code, 200)
        self.assertEqual(lista.data['count'], 1)
        self.assertNotIn('archivo_referencia', lista.data['results'][0])
        secretaria = self.cliente(self.regent)
        self.assertEqual(secretaria.get(f'/api/reportes/ejecuciones/{pk}/').status_code, 404)
        self.assertEqual(secretaria.get(f'/api/reportes/ejecuciones/{pk}/descargar/').status_code, 404)
        self.assertEqual(client.post(f'/api/reportes/ejecuciones/{pk}/archivar/', {}, format='json').status_code, 200)
        ejecucion = EjecucionReporte.objects.get(pk=pk)
        self.assertIsNotNone(ejecucion.archivado_at)
        self.assertTrue((Path(self.settings_root()) / ejecucion.archivo_referencia).exists())
        self.assertEqual(client.get('/api/reportes/ejecuciones/').data['count'], 0)
        self.assertEqual(client.get('/api/reportes/ejecuciones/', {'archivados': 'true'}).data['count'], 1)
        for evento in EventoAuditoria.objects.filter(entidad='REPORTE_EJECUCION', entidad_id=pk):
            self.assertNotIn(self.settings_root(), str(evento.cambios_sanitizados))
            self.assertNotIn('archivo', str(evento.cambios_sanitizados))

    def test_error_de_exportacion_no_deja_archivo(self):
        client = self.cliente(self.director)
        definicion = self.crear(client).data
        with patch('aplicaciones.reportes.views.exportar_csv', side_effect=ValueError('dato sensible')):
            respuesta = client.post('/api/reportes/exportar/', {'definicion_id': definicion['id'], 'formato': 'CSV'}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        ejecucion = EjecucionReporte.objects.get(pk=respuesta.data['ejecucion_id'])
        self.assertEqual(ejecucion.estado, 'ERROR')
        self.assertIsNone(ejecucion.archivo_referencia)
        self.assertEqual(list(Path(self.settings_root()).iterdir()), [])
        self.assertNotIn('dato sensible', str(respuesta.data))

    def test_historial_no_revela_ejecucion_de_otro_colegio(self):
        propietario = self.cliente(self.outsider)
        definicion = self.crear(propietario, nombre='Reporte privado colegio B')
        self.assertEqual(definicion.status_code, 201, definicion.data)
        exportacion = propietario.post('/api/reportes/exportar/', {
            'definicion_id': definicion.data['id'], 'formato': 'CSV',
        }, format='json')
        self.assertEqual(exportacion.status_code, 200)
        pk = exportacion['X-Reporte-Ejecucion']
        ejecucion = EjecucionReporte.objects.get(pk=pk)
        atacante = self.cliente(self.director)
        lista = atacante.get('/api/reportes/ejecuciones/')
        self.assertEqual(lista.status_code, 200)
        self.assertEqual(lista.data['results'], [])
        rutas = [
            atacante.get(f'/api/reportes/ejecuciones/{pk}/'),
            atacante.get(f'/api/reportes/ejecuciones/{pk}/descargar/'),
            atacante.post(f'/api/reportes/ejecuciones/{pk}/archivar/', {}, format='json'),
        ]
        inexistente = atacante.get('/api/reportes/ejecuciones/00000000-0000-0000-0000-000000000000/')
        for respuesta in rutas:
            self.assertEqual(respuesta.status_code, 404)
            self.assertEqual(respuesta.data, inexistente.data)
        for respuesta in [lista, *rutas]:
            texto = str(respuesta.data)
            for dato in ('Reporte privado colegio B', str(ejecucion.pk), ejecucion.archivo_referencia, ejecucion.archivo_checksum):
                self.assertNotIn(dato, texto)
            self.assertNotIn('archivo_tamano', texto)
        ejecucion.refresh_from_db()
        self.assertIsNone(ejecucion.archivado_at)

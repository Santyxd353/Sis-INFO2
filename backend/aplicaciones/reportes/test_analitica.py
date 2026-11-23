from datetime import date, datetime, timezone
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from aplicaciones.academico.models import ResultadoTrimestral
from aplicaciones.estudiantes.models import IncidenteDisciplinario, SesionClase, AsistenciaEstudiante
from aplicaciones.institucion.models import Aula, Modulo
from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import Accion, EventoAuditoria, ModeloPermitido, PermisoPuesto, Puesto
from .models import EjecucionReporte
from .analitica import ErrorSerieAnalitica, calcular_serie


class AnaliticaTests(SchoolFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for recurso, acciones in {'reporte-analitico': ['listar'], 'reporte-ejecucion': ['listar', 'descargar']}.items():
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=recurso)
            for nombre in acciones:
                accion, _ = Accion.objects.get_or_create(nombre=nombre)
                PermisoPuesto.objects.get_or_create(puesto=cls.director.admin.puesto, modelo=modelo, accion=accion)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.director)
        self.filtros = {'unidad_educativa': self.unit.pk, 'calendario_academico': self.calendar.pk}

    def test_matricula_actual_resultados_incidentes_y_privacidad(self):
        ResultadoTrimestral.objects.create(historial_inscripcion=self.enrollment, materia=self.subject,
            periodo=self.period, resultado=80, condicion='APROBADO', calculado_at=datetime(2026, 3, 1, tzinfo=timezone.utc))
        IncidenteDisciplinario.objects.create(historial_inscripcion=self.enrollment,
            fecha=datetime(2026, 3, 1, tzinfo=timezone.utc), tipo='GENERAL', severidad='BAJA', descripcion='Prueba')
        response = self.client.get('/api/reportes/analitica/resumen/', {**self.filtros, 'periodo': self.period.pk})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['indicadores']['matricula_actual'], 1)
        self.assertEqual(response.data['indicadores']['promedio_general'], 80)
        self.assertEqual(response.data['indicadores']['porcentaje_aprobacion'], 100)
        self.assertEqual(response.data['indicadores']['incidentes_total'], 1)
        self.assertIsNone(response.data['indicadores']['porcentaje_asistencia'])
        self.assertEqual(response.data['metadatos']['matricula_actual']['tipo_temporal'], 'ACTUAL')
        self.assertNotIn('HU-RUDE', str(response.data))
        self.assertNotIn('student', str(response.data))

    def test_otro_colegio_no_disponible(self):
        response = self.client.get('/api/reportes/analitica/resumen/', {**self.filtros, 'unidad_educativa': self.other_unit.pk})
        self.assertEqual(response.status_code, 404)

    def test_asistencia_y_periodo(self):
        modulo = Modulo.objects.create(nombre='Bloque', cantidad_aulas=1, unidad_educativa=self.unit)
        aula = Aula.objects.create(nombre='Aula', capacidad=20, modulo=modulo)
        sesion = SesionClase.objects.create(asignacion_docente=self.assignment, fecha=date(2026, 3, 1), profesor_efectivo=self.prof, aula_efectiva=aula)
        AsistenciaEstudiante.objects.create(sesion_clase=sesion, historial_inscripcion=self.enrollment, estado_asistencia='PRESENTE')
        response = self.client.get('/api/reportes/analitica/resumen/', {**self.filtros, 'periodo': self.period.pk})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['indicadores']['porcentaje_asistencia'], 100)
        self.assertEqual(response.data['series']['asistencia_por_estado'][0]['valor'], 1)
        auditoria = EventoAuditoria.objects.filter(entidad='REPORTE_EJECUCION', accion='REPORTAR').latest('pk')
        self.assertNotIn('HU-RUDE', str(auditoria.cambios_sanitizados))
        self.assertNotIn('student', str(auditoria.cambios_sanitizados))

    def test_secretaria_requiere_permiso_y_solo_su_unidad(self):
        puesto, _ = Puesto.objects.get_or_create(nombre='Secretaria')
        self.regent.admin.puesto = puesto
        self.regent.admin.save()
        self.client.force_authenticate(self.regent)
        self.assertEqual(self.client.get('/api/reportes/analitica/resumen/', self.filtros).status_code, 403)
        PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=ModeloPermitido.objects.get(nombre='reporte-analitico'), accion=Accion.objects.get(nombre='listar'))
        self.assertEqual(self.client.get('/api/reportes/analitica/resumen/', self.filtros).status_code, 200)
        self.assertIn(self.client.get('/api/reportes/analitica/resumen/', {**self.filtros, 'unidad_educativa': self.other_unit.pk}).status_code, (400, 403, 404))

    def test_exportacion_privada_historial(self):
        with TemporaryDirectory() as carpeta, override_settings(REPORTES_PRIVATE_ROOT=carpeta):
            for formato in ('CSV', 'PDF'):
                response = self.client.post('/api/reportes/analitica/exportar/', {'filtros': self.filtros, 'formato': formato}, format='json')
                self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
                item = EjecucionReporte.objects.get(pk=response['X-Reporte-Ejecucion'])
                self.assertEqual(item.tipo, 'ANALITICO')
                self.assertEqual(item.estado, 'COMPLETADO')
                self.assertEqual(self.client.get(f'/api/reportes/ejecuciones/{item.pk}/descargar/').status_code, 200)
            self.assertEqual(self.client.get('/api/reportes/ejecuciones/').data['count'], 2)

    def test_error_controlado_en_serie_conserva_los_demas_datos(self):
        def calcular(qs, campo, etiqueta):
            if campo == 'sesion_clase__fecha':
                raise ErrorSerieAnalitica('detalle interno SQL')
            return calcular_serie(qs, campo, etiqueta)
        with patch('aplicaciones.reportes.analitica.calcular_serie', side_effect=calcular):
            respuesta = self.client.get('/api/reportes/analitica/resumen/', self.filtros)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['indicadores']['matricula_actual'], 1)
        self.assertEqual(respuesta.data['series']['matricula_por_curso'][0]['valor'], 1)
        self.assertIsNone(respuesta.data['series']['asistencia_por_fecha'])
        self.assertEqual(respuesta.data['metadatos']['errores_parciales'], [
            {'componente': 'asistencia_por_fecha', 'mensaje': 'No fue posible calcular esta serie.'},
        ])
        self.assertNotIn('detalle interno', str(respuesta.data))

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from datetime import date

from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import Accion, ModeloPermitido, PermisoPuesto
from aplicaciones.academico.models import ResultadoTrimestral
from aplicaciones.estudiantes.models import AsistenciaEstudiante, SesionClase
from aplicaciones.institucion.models import Aula, Modulo
from .fuentes_operativas import catalogo_operativo, ejecutar_fuente


class FuentesOperativasTests(SchoolFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        recurso, _ = ModeloPermitido.objects.get_or_create(nombre='reporte-ejecucion')
        accion, _ = Accion.objects.get_or_create(nombre='ejecutar')
        PermisoPuesto.objects.get_or_create(puesto=cls.director.admin.puesto, modelo=recurso, accion=accion)

    def test_catalogo_publica_cinco_fuentes_operativas_sin_rutas(self):
        catalogo = catalogo_operativo()
        self.assertEqual(
            {item['codigo'] for item in catalogo},
            {'ESTUDIANTES_INSCRITOS', 'ASISTENCIA_RESUMEN', 'RENDIMIENTO_ACADEMICO', 'INCIDENTES_DISCIPLINARIOS'},
        )
        self.assertNotIn('__', str(catalogo))
        self.assertNotIn('modelo', str(catalogo).lower())

    def test_alcance_antes_de_filtros_y_usuario_no_autorizado(self):
        especificacion = {'columnas': ['estudiante_id', 'nombre'], 'filtros': [], 'orden': []}
        _, filas, exceso = ejecutar_fuente(self.director, 'ESTUDIANTES_INSCRITOS', especificacion)
        self.assertEqual(filas, [[self.student.pk, 'student Test']])
        self.assertFalse(exceso)
        especificacion['filtros'] = [{'campo': 'unidad', 'operador': 'eq', 'valor': self.other_unit.pk}]
        self.assertEqual(ejecutar_fuente(self.director, 'ESTUDIANTES_INSCRITOS', especificacion)[1], [])
        with self.assertRaises(PermissionDenied):
            ejecutar_fuente(self.student_user, 'ESTUDIANTES_INSCRITOS', especificacion)

    def test_no_acepta_rutas_de_cliente(self):
        from django.core.exceptions import ValidationError
        spec = {'columnas': ['unidad__colegio'], 'filtros': [], 'orden': []}
        with self.assertRaises(ValidationError):
            ejecutar_fuente(self.director, 'INCIDENTES_DISCIPLINARIOS', spec)

    def test_fuentes_academicas_y_asistencia_devuelven_datos_del_alcance(self):
        modulo = Modulo.objects.create(nombre='Módulo reportes', cantidad_aulas=1, colegio_fk=self.school, unidad_educativa=self.unit)
        aula = Aula.objects.create(modulo=modulo, nombre='A-1', capacidad=30)
        sesion = SesionClase.objects.create(
            asignacion_docente=self.assignment, fecha=date(2026, 3, 2), profesor_efectivo=self.prof, aula_efectiva=aula,
        )
        AsistenciaEstudiante.objects.create(
            sesion_clase=sesion, historial_inscripcion=self.enrollment, estado_asistencia='PRESENTE',
        )
        ResultadoTrimestral.objects.create(
            historial_inscripcion=self.enrollment, materia=self.subject, periodo=self.period,
            resultado=60, condicion='APROBADO', calculado_at='2026-03-02T00:00:00Z',
        )
        casos = {
            'ASISTENCIA_RESUMEN': ['nombre', 'total', 'presentes'],
            'RENDIMIENTO_ACADEMICO': ['nombre', 'materia', 'promedio'],
        }
        for codigo, columnas in casos.items():
            with self.subTest(codigo=codigo):
                _, filas, exceso = ejecutar_fuente(
                    self.director, codigo, {'columnas': columnas, 'filtros': [], 'orden': []},
                )
                self.assertEqual(len(filas), 1)
                self.assertFalse(exceso)

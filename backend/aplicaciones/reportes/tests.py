from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import Accion, Admin, ModeloPermitido, PermisoPuesto, Puesto, Rol, Usuario
from .fuentes import catalogo_publico, resolver_fuente
from .models import EjecucionReporte, ReporteDefinicion
from .seguridad import tiene_permiso, validar_contexto


class ReportesEstructuraTests(SchoolFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        recurso, _ = ModeloPermitido.objects.get_or_create(nombre='reporte-definicion')
        accion, _ = Accion.objects.get_or_create(nombre='crear')
        PermisoPuesto.objects.get_or_create(puesto=cls.director.admin.puesto, modelo=recurso, accion=accion)

    @staticmethod
    def otorgar_permisos_operativos_secretaria(puesto):
        recursos = {
            'reporte-definicion': ('listar', 'crear', 'editar', 'archivar'),
            'reporte-ejecucion': ('listar', 'ejecutar', 'descargar'),
        }
        for nombre_recurso, acciones in recursos.items():
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=nombre_recurso)
            for nombre_accion in acciones:
                accion, _ = Accion.objects.get_or_create(nombre=nombre_accion)
                PermisoPuesto.objects.get_or_create(
                    puesto=puesto, modelo=modelo, accion=accion,
                )

    def definicion(self, **kwargs):
        datos = dict(colegio=self.school, unidad_educativa=self.unit, propietario=self.director,
                     nombre='  Mi   reporte  ', descripcion='Reporte institucional de prueba',
                     tipo='OPERATIVO', codigo_fuente='ESTUDIANTES_INSCRITOS')
        datos.update(kwargs)
        return ReporteDefinicion.objects.create(**datos)

    def ejecucion(self, **kwargs):
        datos = dict(colegio=self.school, unidad_educativa=self.unit, solicitante=self.director,
                     tipo='OPERATIVO', fuente_codigo='ESTUDIANTES_INSCRITOS')
        datos.update(kwargs)
        return EjecucionReporte.objects.create(**datos)

    def test_creacion_y_tablas_fisicas(self):
        definicion = self.definicion()
        ejecucion = self.ejecucion(definicion=definicion)
        self.assertEqual(definicion.nombre, 'Mi reporte')
        self.assertEqual(definicion.descripcion, 'Reporte institucional de prueba')
        self.assertIsNotNone(ejecucion.id)
        tablas = set(connection.introspection.table_names())
        self.assertEqual({t for t in tablas if t.startswith('reportes_reporte_definicion') or t.startswith('reportes_ejecucion_reporte')}, {'reportes_reporte_definicion', 'reportes_ejecucion_reporte'})

    def test_tenant_y_propietario(self):
        with self.assertRaises(ValidationError):
            self.definicion(unidad_educativa=self.other_unit)
        with self.assertRaises(ValidationError):
            self.definicion(propietario=self.outsider)
        definicion = self.definicion()
        with self.assertRaises(ValidationError):
            self.ejecucion(definicion=definicion, colegio=self.other_unit.colegio, unidad_educativa=self.other_unit)
        with self.assertRaises(ValidationError):
            self.ejecucion(definicion=definicion, unidad_educativa=None)

    def test_unicidad_y_archivo(self):
        primero = self.definicion()
        with self.assertRaises(ValidationError):
            self.definicion(nombre='mi reporte')
        primero.archivar()
        self.assertIsNotNone(primero.archivado_at)
        self.definicion(nombre='mi reporte')
        with self.assertRaises(ValidationError):
            primero.delete()

    def test_json_y_qbe(self):
        for valor in ({'token': 'x'}, {'filtro': {'sql': 'x'}}, {'campo': 'SELECT * FROM usuario'}, {'audio': 'x'}):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                self.definicion(especificacion=valor)
        with self.assertRaises(ValidationError):
            self.definicion(tipo='QBE', especificacion={})
        with self.assertRaises(ValidationError):
            self.definicion(tipo='QBE', especificacion={'campos': ['unidad__colegio']})

    def test_estados_y_sanitizacion(self):
        for datos in ({'estado': 'COMPLETADO'}, {'estado': 'ERROR'}, {'filas_resultado': -1},
                      {'archivo_tamano': -1}, {'estado': 'ERROR', 'error_sanitizado': 'Traceback password'},
                      {'actor_snapshot': {'password': 'x'}}, {'parametros_sanitizados': {'token': 'x'}}):
            with self.subTest(datos=datos), self.assertRaises(ValidationError):
                self.ejecucion(**datos)
        self.ejecucion(estado='COMPLETADO', finalizada_at=timezone.now())
        self.ejecucion(estado='ERROR', error_sanitizado='ERROR_INTERNO')

    def test_permisos_y_alcance(self):
        self.assertTrue(tiene_permiso(self.director, 'reporte-definicion', 'crear'))
        self.assertFalse(tiene_permiso(self.teacher, 'reporte-qbe', 'ejecutar'))
        self.assertFalse(tiene_permiso(self.student_user, 'reporte-definicion', 'crear'))
        self.assertEqual(validar_contexto(self.director, self.school.pk)['tipo'], 'COLEGIO')
        self.assertEqual(validar_contexto(self.teacher, self.school.pk, self.unit.pk)['tipo'], 'PERSONAL')
        with self.assertRaises(PermissionDenied):
            validar_contexto(self.teacher, self.school.pk, self.other_unit.pk)
        puesto, _ = Puesto.objects.get_or_create(nombre='Secretaria')
        self.otorgar_permisos_operativos_secretaria(puesto)
        self.regent.admin.puesto = puesto
        self.regent.admin.save()
        self.assertTrue(tiene_permiso(self.regent, 'reporte-definicion', 'crear'))
        self.assertEqual(validar_contexto(self.regent, self.school.pk, self.unit.pk)['tipo'], 'UNIDAD')
        with self.assertRaises(PermissionDenied):
            validar_contexto(self.regent, self.school.pk, self.other_unit.pk)
        rol, _ = Rol.objects.get_or_create(nombre='SuperAdmin')
        superusuario = Usuario.objects.create_user(ci='superhu', username='superhu', email='superhu@example.com', nombre='Super', apellido='Prueba', rol=rol)
        self.assertFalse(tiene_permiso(superusuario, 'reporte-definicion', 'crear'))
        with self.assertRaises(PermissionDenied):
            validar_contexto(superusuario, None)

    def test_puesto_secretaria_nuevo_recibe_permisos_operativos(self):
        puesto = Puesto.objects.create(nombre='Secretaría')
        self.assertTrue(
            PermisoPuesto.objects.filter(
                puesto=puesto,
                modelo__nombre='reporte-definicion',
                accion__nombre='crear',
            ).exists()
        )
        self.assertEqual(
            PermisoPuesto.objects.filter(
                puesto=puesto, modelo__nombre__in=(
                    'reporte-qbe', 'reporte-analitico', 'reporte-voz',
                ),
            ).count(),
            0,
        )

    def test_fuentes_no_exponen_rutas(self):
        for fuente in catalogo_publico():
            self.assertNotIn('modelo', fuente)
            self.assertNotIn('tabla', fuente)
            self.assertNotIn('orm_path', fuente)
            self.assertIsNotNone(resolver_fuente(fuente['codigo']))

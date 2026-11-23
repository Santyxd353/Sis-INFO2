from django.db import connection
from django.apps import apps
from rest_framework import status
from rest_framework.test import APITestCase

from aplicaciones.usuarios.models import Usuario

from .models import Colegio, ExportacionSIE, UnidadEducativa
from aplicaciones.calendario.models import CalendarioAcademico
from django.core.exceptions import ValidationError


class ColegioExpansionTests(APITestCase):
    def setUp(self):
        self.colegio_a = Colegio.objects.create(
            nombre='Colegio legado A',
            direccion='Dirección A',
            telefono='70000001',
        )
        self.colegio_b = Colegio.objects.create(
            nombre='Colegio legado B',
            direccion='Dirección B',
            telefono='70000002',
        )

    def test_conserva_colegios_pk_campos_anteriores_y_expansion_nullable(self):
        ids_esperados = [self.colegio_a.pk, self.colegio_b.pk]
        nombres_esperados = ['Colegio legado A', 'Colegio legado B']

        colegios = Colegio.objects.order_by('pk')

        self.assertEqual(list(colegios.values_list('pk', flat=True)), ids_esperados)
        self.assertEqual(list(colegios.values_list('nombre', flat=True)), nombres_esperados)
        for colegio in colegios:
            self.assertTrue(hasattr(colegio, 'logo'))
            self.assertTrue(hasattr(colegio, 'super_admin_fk'))
            self.assertIsNone(colegio.codigo_tenant)
            self.assertIsNone(colegio.tipo_subsistema)
            self.assertEqual(colegio.zona_horaria, 'America/La_Paz')
            self.assertEqual(colegio.moneda, 'BOB')
            self.assertEqual(colegio.estado, Colegio.Estado.ACTIVO)
            self.assertIsNotNone(colegio.created_at)
            self.assertIsNotNone(colegio.updated_at)

    def test_endpoint_conserva_contrato_actual_y_aplica_defaults(self):
        usuario = Usuario.objects.create_superuser(
            ci='CI-COLEGIO-EXPAND',
            email='colegio-expand@example.com',
            nombre='Admin',
            apellido='Prueba',
            username='admin_colegio_expand',
            fecha_nacimiento='1990-01-01',
            password='Clave-Segura-123',
        )
        self.client.force_authenticate(usuario)

        response = self.client.post(
            '/api/institucion/colegios/',
            {
                'nombre': 'Colegio contrato existente',
                'direccion': 'Dirección de prueba',
                'telefono': '70000003',
                'email': 'contrato@example.com',
                'sitio_web': 'https://example.com',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            set(response.data),
            {'id', 'nombre', 'direccion', 'telefono', 'email', 'sitio_web'},
        )
        colegio = Colegio.objects.get(pk=response.data['id'])
        self.assertEqual(colegio.zona_horaria, 'America/La_Paz')
        self.assertEqual(colegio.moneda, 'BOB')
        self.assertEqual(colegio.estado, Colegio.Estado.ACTIVO)
        self.assertIsNone(colegio.codigo_tenant)
        self.assertIsNone(colegio.tipo_subsistema)

    def test_solo_crea_tablas_autorizadas_hasta_sprint2(self):
        campos_unidad = {field.name for field in UnidadEducativa._meta.local_fields}
        self.assertEqual(
            campos_unidad,
            {
                'id',
                'codigo_sie',
                'turno',
                'nombre',
                'direccion',
                'telefono',
                'nivel',
                'codigo_interno',
                'codigo_rue',
                'correo',
                'umbral_riesgo_asistencia',
                'umbral_riesgo_promedio',
                'umbral_riesgo_incidentes',
                'riesgo_version',
                'sie_habilitado',
                'sie_version',
                'sie_config',
                'estado',
                'created_at',
                'updated_at',
                'eliminado_at',
                'colegio',
            },
        )

        self.assertTrue(UnidadEducativa._meta.get_field('colegio').null)
        self.assertTrue(UnidadEducativa._meta.get_field('codigo_sie').unique)

        with connection.cursor() as cursor:
            columnas_unidad = connection.introspection.get_table_description(
                cursor, UnidadEducativa._meta.db_table
            )
        self.assertEqual(len(columnas_unidad), 22)

        tablas = set(connection.introspection.table_names())
        tablas_bloque1 = {
            'auditoria_evento',
            'academico_asignacion_docente',
            'horarios_bloque',
            'horarios_clase',
            'asistencia_sesion_clase',
            'asistencia_estudiante',
            'disciplina_incidente',
            'disciplina_accion',
        }
        self.assertEqual(tablas.intersection(tablas_bloque1), tablas_bloque1)

        tablas_bloque2 = {
            'evaluacion_configuracion',
            'evaluacion_dimension',
            'evaluacion_actividad',
            'evaluacion_calificacion',
            'evaluacion_correccion',
            'evaluacion_resultado_trimestral',
            'evaluacion_resultado_anual',
            'reportes_documento_academico',
            'reportes_riesgo_academico',
            'sie_exportacion',
        }
        self.assertEqual(tablas.intersection(tablas_bloque2), tablas_bloque2)
        self.assertEqual(len(tablas.intersection(tablas_bloque1 | tablas_bloque2)), 18)

        # HU-SE01: las tablas de suscripciones SaaS sí existen (sprint 3).
        self.assertTrue({
            'suscripciones_plan',
            'suscripciones_suscripcion',
            'suscripciones_pago',
        }.issubset(tablas))

        tablas_sprint3 = {
            'finanzas_concepto',
            'comunicaciones_comunicado',
            'comunicaciones_notificacion',
            'operaciones_ejecucion_respaldo',
        }
        self.assertFalse(
            tablas.intersection(tablas_sprint3)
        )

    def test_exportacion_sie_coherencia_institucional(self):
        calendario = CalendarioAcademico.objects.create(
            unidad_educativa=UnidadEducativa.objects.create(
                codigo_sie='SIE-EXPORTACION', turno='TARDE', nombre='Unidad SIE',
                colegio=self.colegio_a,
            ),
            año=2029,
            fecha_inicio='2029-02-01',
            fecha_fin='2029-11-30',
        )
        exportacion = ExportacionSIE(
            unidad_educativa=calendario.unidad_educativa,
            calendario_academico=calendario,
            tipo='ESTUDIANTES',
            version=1,
        )
        exportacion.full_clean()
        exportacion.save()
        self.assertEqual(exportacion.configuracion_snapshot, {})
        self.assertEqual(exportacion.errores_sanitizados, [])

        exportacion_invalida = ExportacionSIE(
            unidad_educativa=UnidadEducativa.objects.create(
                codigo_sie='SIE-EXPORTACION-OTRA', turno='TARDE', nombre='Otra unidad',
                colegio=self.colegio_b,
            ),
            calendario_academico=calendario,
            tipo='ESTUDIANTES',
            version=2,
        )
        with self.assertRaises(ValidationError):
            exportacion_invalida.full_clean()

    def test_unidad_educativa_campos_nuevos_y_defaults(self):
        unidad = UnidadEducativa.objects.create(
            codigo_sie='SIE-EXPAND-01',
            turno='TARDE',
            nombre='Unidad expandida',
        )

        self.assertIsNone(unidad.codigo_interno)
        self.assertIsNone(unidad.codigo_rue)
        self.assertIsNone(unidad.correo)
        self.assertIsNone(unidad.umbral_riesgo_asistencia)
        self.assertIsNone(unidad.umbral_riesgo_promedio)
        self.assertIsNone(unidad.umbral_riesgo_incidentes)
        self.assertIsNone(unidad.riesgo_version)
        self.assertIsNone(unidad.sie_version)
        self.assertIsNone(unidad.eliminado_at)
        self.assertEqual(unidad.estado, 'ACTIVO')
        self.assertFalse(unidad.sie_habilitado)
        self.assertEqual(unidad.sie_config, {})

    def test_unidad_educativa_json_independiente_y_timestamps(self):
        unidad_a = UnidadEducativa.objects.create(
            codigo_sie='SIE-EXPAND-02', turno='TARDE', nombre='Unidad A',
        )
        unidad_b = UnidadEducativa.objects.create(
            codigo_sie='SIE-EXPAND-03', turno='NOCHE', nombre='Unidad B',
        )

        unidad_a.sie_config['formato'] = 'prueba'
        self.assertEqual(unidad_b.sie_config, {})
        self.assertIsNot(unidad_a.sie_config, unidad_b.sie_config)
        self.assertIsNotNone(unidad_a.created_at)
        self.assertIsNotNone(unidad_a.updated_at)

        created_at = unidad_a.created_at
        updated_at = unidad_a.updated_at
        unidad_a.nombre = 'Unidad A actualizada'
        unidad_a.save(update_fields=['nombre'])
        unidad_a.refresh_from_db()

        self.assertEqual(unidad_a.created_at, created_at)
        self.assertGreaterEqual(unidad_a.updated_at, updated_at)

    def test_endpoint_unidad_conserva_contrato_heredado(self):
        usuario = Usuario.objects.create_superuser(
            ci='CI-UNIDAD-EXPAND',
            email='unidad-expand@example.com',
            nombre='Admin',
            apellido='Prueba',
            username='admin_unidad_expand',
            fecha_nacimiento='1990-01-01',
            password='Clave-Segura-123',
        )
        self.client.force_authenticate(usuario)

        response = self.client.post(
            '/api/institucion/unidades-educativas/',
            {
                'codigo_sie': 'SIE-EXPAND-04',
                'turno': 'TARDE',
                'nombre': 'Unidad contrato heredado',
                'direccion': 'Dirección de prueba',
                'telefono': '70000004',
                'nivel': 'secundario',
                'colegio_id': self.colegio_a.pk,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            set(response.data),
            {
                'id', 'codigo_sie', 'turno', 'nombre', 'direccion', 'telefono',
                'nivel', 'colegio', 'colegio_id',
            },
        )
        self.assertEqual(response.data['codigo_sie'], 'SIE-EXPAND-04')
        self.assertEqual(response.data['turno'], 'TARDE')
        self.assertEqual(response.data['nivel'], 'secundario')

    def test_unidad_educativa_alcance_estructural(self):
        unidad = UnidadEducativa.objects.create(
            codigo_sie='SIE-EXPAND-05',
            turno='COMPLETO',
            nombre='Unidad estructural',
            colegio=self.colegio_a,
        )

        self.assertIn(unidad, self.colegio_a.unidades_educativas.all())
        self.assertTrue(UnidadEducativa._meta.get_field('colegio').null)
        self.assertTrue(UnidadEducativa._meta.get_field('codigo_sie').unique)

        modelos = {
            model.__name__
            for app_config in apps.get_app_configs()
            for model in app_config.get_models()
        }
        self.assertFalse(
            {'UnidadEducativaNivel', 'Persona', 'MembresiaColegio', 'AsignacionRol'}
            & modelos
        )

        tablas = set(connection.introspection.table_names())
        self.assertFalse(
            {
                'institucion_unidad_nivel',
                'personal_persona',
                'usuarios_membresia_colegio',
                'usuarios_asignacion_rol',
                'comunicaciones_comunicado',
            }
            & tablas
        )

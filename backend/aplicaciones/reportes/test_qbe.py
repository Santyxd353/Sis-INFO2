from unittest.mock import patch
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import Accion, EventoAuditoria, ModeloPermitido, PermisoPuesto, PermisoRol, Puesto
from .models import EjecucionReporte, ReporteDefinicion


class QbeTests(SchoolFixture, TestCase):
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
        # Estos casos verifican explícitamente el comportamiento sin acceso a personal.
        PermisoPuesto.objects.filter(puesto=cls.director.admin.puesto, modelo__nombre__in=('profesor', 'usuario'), accion__nombre='listar').delete()
        PermisoRol.objects.filter(rol=cls.director.rol, modelo__nombre__in=('profesor', 'usuario'), accion__nombre='listar').delete()
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='reporte-definicion')
        for nombre in ('crear', 'editar', 'archivar'):
            accion, _ = Accion.objects.get_or_create(nombre=nombre)
            PermisoPuesto.objects.get_or_create(puesto=cls.director.admin.puesto, modelo=modelo, accion=accion)
        for accion_nombre in ('validar', 'ejecutar'):
            recurso, _ = ModeloPermitido.objects.get_or_create(nombre='reporte-qbe')
            accion, _ = Accion.objects.get_or_create(nombre=accion_nombre)
            PermisoPuesto.objects.get_or_create(puesto=cls.director.admin.puesto, modelo=recurso, accion=accion)
        recurso, _ = ModeloPermitido.objects.get_or_create(nombre='reporte-ejecucion')
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        PermisoPuesto.objects.get_or_create(puesto=cls.director.admin.puesto, modelo=recurso, accion=accion)

    def cliente(self, user):
        client = APIClient(); client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(user)))
        return client

    def spec(self, condiciones=None):
        return {'columnas': ['nombre', 'curso'], 'condiciones': condiciones or {'logica': 'AND', 'condiciones': []}, 'orden': []}

    def crear(self, client, **extra):
        data = {'nombre': 'Consulta QBE', 'codigo_fuente': 'ESTUDIANTES_INSCRITOS', 'especificacion': self.spec()}
        data.update(extra)
        return client.post('/api/reportes/qbe/definiciones/', data, format='json')

    def test_catalogo_permisos_y_consulta_valida(self):
        self.assertEqual(self.cliente(self.regent).get('/api/reportes/qbe/catalogo/').status_code, 403)
        self.assertEqual(self.cliente(self.teacher).get('/api/reportes/qbe/catalogo/').status_code, 403)
        client = self.cliente(self.director)
        catalogo = client.get('/api/reportes/qbe/catalogo/')
        self.assertEqual(catalogo.status_code, 200)
        self.assertEqual(len(catalogo.data['results']), 4)
        creado = self.crear(client)
        self.assertEqual(creado.status_code, 201, creado.data)
        respuesta = client.post('/api/reportes/qbe/previsualizar/', {'definicion_id': creado.data['id']}, format='json')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['cantidad'], 1)
        ejecucion = EjecucionReporte.objects.get(pk=respuesta.data['ejecucion_id'])
        self.assertEqual(ejecucion.tipo, 'QBE')
        self.assertEqual(ejecucion.estado, 'COMPLETADO')

    def test_fuentes_personal_y_filtro_genero_con_permiso(self):
        client = self.cliente(self.director)
        inicial = client.get('/api/reportes/qbe/catalogo/').data['results']
        self.assertNotIn('DOCENTES', [f['codigo'] for f in inicial])
        self.assertNotIn('PERSONAL_ADMINISTRATIVO', [f['codigo'] for f in inicial])
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        for nombre in ('profesor', 'usuario'):
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=nombre)
            PermisoPuesto.objects.get_or_create(puesto=self.director.admin.puesto, modelo=modelo, accion=accion)
        catalogo = {f['codigo']: f for f in client.get('/api/reportes/qbe/catalogo/').data['results']}
        from aplicaciones.usuarios.models import Usuario
        for codigo in ('ESTUDIANTES_INSCRITOS', 'DOCENTES', 'PERSONAL_ADMINISTRATIVO'):
            filtro = next(f for f in catalogo[codigo]['filtros'] if f['campo'] == 'genero')
            self.assertEqual(filtro['opciones'], [{'valor': v, 'etiqueta': e} for v, e in Usuario._meta.get_field('sexo').choices])
            spec = {'columnas': ['genero'], 'condiciones': {'campo': 'genero', 'operador': 'eq', 'valor': Usuario.SEXO_MASCULINO}, 'orden': []}
            respuesta = client.post('/api/reportes/qbe/previsualizar/', {'codigo_fuente': codigo, 'especificacion': spec}, format='json')
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertGreater(respuesta.data['cantidad'], 0)
            self.assertTrue(all(fila == [Usuario.SEXO_MASCULINO] for fila in respuesta.data['filas']))
            creada = self.crear(client, codigo_fuente=codigo, nombre='QBE ' + codigo, especificacion=spec)
            self.assertEqual(creada.status_code, 201, creada.data)
            for formato in ('CSV', 'PDF'):
                exportada = client.post('/api/reportes/qbe/exportar/', {'definicion_id': creada.data['id'], 'formato': formato}, format='json')
                self.assertEqual(exportada.status_code, 200, getattr(exportada, 'data', None))

    def test_personal_no_amplia_alcance_por_unidad_manipulada(self):
        from aplicaciones.personal.models import Profesor
        from aplicaciones.usuarios.models import Usuario
        externo = Usuario.objects.create_user(ci='externo', email='externo@example.com', nombre='Externo', apellido='Docente', username='externo', rol=self.teacher.rol, unidad=self.other_unit)
        Profesor.objects.create(usuario=externo, unidad=self.other_unit)
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        for nombre in ('profesor', 'usuario'):
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=nombre)
            PermisoPuesto.objects.get_or_create(puesto=self.director.admin.puesto, modelo=modelo, accion=accion)
        client = self.cliente(self.director)
        for codigo in ('DOCENTES', 'PERSONAL_ADMINISTRATIVO'):
            spec = {'columnas': ['nombre_completo'], 'condiciones': {'campo': 'unidad', 'operador': 'eq', 'valor': self.other_unit.pk}, 'orden': []}
            respuesta = client.post('/api/reportes/qbe/previsualizar/', {'codigo_fuente': codigo, 'especificacion': spec}, format='json')
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertEqual(respuesta.data['filas'], [])

    def test_secretaria_consulta_personal_solo_en_su_unidad(self):
        puesto, _ = Puesto.objects.get_or_create(nombre='Secretaria')
        self.regent.admin.puesto = puesto
        self.regent.admin.save()
        for recurso, acciones in {'reporte-qbe': ('ejecutar',), 'profesor': ('listar',), 'usuario': ('listar',)}.items():
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=recurso)
            for nombre in acciones:
                accion, _ = Accion.objects.get_or_create(nombre=nombre)
                PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)
        cliente = self.cliente(self.regent)
        for codigo in ('DOCENTES', 'PERSONAL_ADMINISTRATIVO'):
            spec = {'columnas': ['nombre_completo'], 'condiciones': {'campo': 'unidad', 'operador': 'eq', 'valor': self.other_unit.pk}, 'orden': []}
            respuesta = cliente.post('/api/reportes/qbe/previsualizar/', {'codigo_fuente': codigo, 'especificacion': spec}, format='json')
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertEqual(respuesta.data['filas'], [])

    def test_catalogo_y_filtro_puestos_respetan_colegio_y_unidad(self):
        from aplicaciones.institucion.models import UnidadEducativa
        from aplicaciones.usuarios.models import Admin, Usuario
        segunda = UnidadEducativa.objects.create(colegio=self.school, codigo_sie='HU-C', turno='TARDE', nombre='Unidad C')
        puesto_segundo = Puesto.objects.create(nombre='Puesto Unidad C')
        puesto_externo = Puesto.objects.create(nombre='Puesto otro colegio')
        for ci, unidad, puesto in [('admin-c', segunda, puesto_segundo), ('admin-b', self.other_unit, puesto_externo)]:
            usuario = Usuario.objects.create_user(ci=ci, email=f'{ci}@example.com', nombre=ci, apellido='Test', username=ci, rol=self.director.rol, unidad=unidad)
            Admin.objects.create(usuario=usuario, puesto=puesto, unidad=unidad, colegio=unidad.colegio)
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        recurso, _ = ModeloPermitido.objects.get_or_create(nombre='usuario')
        PermisoPuesto.objects.get_or_create(puesto=self.director.admin.puesto, modelo=recurso, accion=accion)
        director = self.cliente(self.director)
        def opciones(cliente):
            fuentes = cliente.get('/api/reportes/qbe/catalogo/').data['results']
            admin = next(f for f in fuentes if f['codigo'] == 'PERSONAL_ADMINISTRATIVO')
            return next(f for f in admin['filtros'] if f['campo'] == 'puesto')['opciones']
        nombres = {o['etiqueta'] for o in opciones(director)}
        self.assertIn(puesto_segundo.nombre, nombres)
        self.assertNotIn(puesto_externo.nombre, nombres)
        secretaria, _ = Puesto.objects.get_or_create(nombre='Secretaria')
        self.regent.admin.puesto = secretaria; self.regent.admin.save()
        for recurso_nombre, nombres_accion in {'usuario': ('listar',), 'reporte-qbe': ('validar', 'ejecutar')}.items():
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=recurso_nombre)
            for nombre_accion in nombres_accion:
                accion_permiso, _ = Accion.objects.get_or_create(nombre=nombre_accion)
                PermisoPuesto.objects.get_or_create(puesto=secretaria, modelo=modelo, accion=accion_permiso)
        nombres_unidad = {o['etiqueta'] for o in opciones(self.cliente(self.regent))}
        self.assertNotIn(puesto_segundo.nombre, nombres_unidad)
        self.assertNotIn(puesto_externo.nombre, nombres_unidad)
        self.assertIn(secretaria.nombre, nombres_unidad)
        def consultar(operador, valor):
            spec = {'columnas': ['puesto'], 'condiciones': {'campo': 'puesto', 'operador': operador, 'valor': valor}, 'orden': []}
            return director.post('/api/reportes/qbe/previsualizar/', {'codigo_fuente': 'PERSONAL_ADMINISTRATIVO', 'especificacion': spec}, format='json')
        self.assertEqual(consultar('eq', puesto_segundo.pk).data['filas'], [[puesto_segundo.nombre]])
        self.assertIn([puesto_segundo.nombre], consultar('in', [puesto_segundo.pk, secretaria.pk]).data['filas'])
        respuesta = consultar('eq', puesto_externo.pk)
        self.assertEqual(respuesta.status_code, 400)
        self.assertNotIn(puesto_externo.nombre, str(respuesta.data))

    def test_identificadores_requieren_permiso_y_no_se_registran_en_auditoria(self):
        client = self.cliente(self.director)
        recurso, _ = ModeloPermitido.objects.get_or_create(nombre='estudiante')
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        permisos = PermisoPuesto.objects.filter(puesto=self.director.admin.puesto, modelo=recurso, accion=accion)
        permisos.delete()
        spec = {**self.spec(), 'columnas': ['nombre', 'curso', 'unidad', 'activo', 'ci', 'rude']}
        payload = {'codigo_fuente': 'ESTUDIANTES_INSCRITOS', 'especificacion': spec}
        catalogo = client.get('/api/reportes/qbe/catalogo/').data['results']
        estudiantes = next(f for f in catalogo if f['codigo'] == 'ESTUDIANTES_INSCRITOS')
        self.assertFalse({'ci', 'rude'} & {c['campo'] for c in estudiantes['columnas']})
        self.assertEqual(client.post('/api/reportes/qbe/previsualizar/', payload, format='json').status_code, 403)
        PermisoPuesto.objects.create(puesto=self.director.admin.puesto, modelo=recurso, accion=accion)
        catalogo = client.get('/api/reportes/qbe/catalogo/').data['results']
        estudiantes = next(f for f in catalogo if f['codigo'] == 'ESTUDIANTES_INSCRITOS')
        self.assertTrue(set(spec['columnas']) <= {c['campo'] for c in estudiantes['columnas']})
        creada = self.crear(client, especificacion=spec)
        self.assertEqual(creada.status_code, 201, creada.data)
        guardada = client.post('/api/reportes/qbe/previsualizar/', {'definicion_id': creada.data['id']}, format='json')
        self.assertEqual(guardada.status_code, 200, guardada.data)
        respuesta = client.post('/api/reportes/qbe/previsualizar/', payload, format='json')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['cantidad'], 1)
        ejecucion = EjecucionReporte.objects.get(pk=respuesta.data['ejecucion_id'])
        auditorias = EventoAuditoria.objects.filter(entidad='REPORTE_EJECUCION', entidad_id=str(ejecucion.pk))
        for fila in respuesta.data['filas']:
            for valor in fila[-2:]:
                if valor:
                    self.assertNotIn(str(valor), str(list(auditorias.values_list('cambios_sanitizados', flat=True))))

    def test_valida_campos_operadores_limites_e_inyeccion(self):
        client = self.cliente(self.director)
        invalidos = [
            self.spec({'campo': 'usuario__password', 'operador': 'eq', 'valor': 'x'}),
            self.spec({'campo': 'activo', 'operador': 'gte', 'valor': True}),
            self.spec({'campo': 'curso', 'operador': 'eq', 'valor': 'SELECT * FROM usuario'}),
            self.spec({'logica': 'AND', 'condiciones': [{'campo': 'curso', 'operador': 'eq', 'valor': 1}] * 11}),
            self.spec({'logica': 'AND', 'condiciones': [{'logica': 'OR', 'condiciones': [{'logica': 'AND', 'condiciones': [{'campo': 'curso', 'operador': 'eq', 'valor': 1}]}]}]}),
        ]
        for spec in invalidos:
            with self.subTest(spec=spec):
                self.assertEqual(self.crear(client, nombre=f'QBE {len(str(spec))}', especificacion=spec).status_code, 400)
        self.assertEqual(self.crear(client, especificacion={**self.spec(), 'orden': [{'campo': 'curso', 'direccion': 'asc'}] * 4}).status_code, 400)

    def test_aislamiento_y_definicion_manipulada(self):
        client = self.cliente(self.director)
        creada = self.crear(client, especificacion=self.spec({'campo': 'unidad', 'operador': 'eq', 'valor': self.other_unit.pk}))
        self.assertEqual(creada.status_code, 201, creada.data)
        vista = client.post('/api/reportes/qbe/previsualizar/', {'definicion_id': creada.data['id']}, format='json')
        self.assertEqual(vista.status_code, 200, vista.data)
        self.assertEqual(vista.data['cantidad'], 0)
        ReporteDefinicion.objects.filter(pk=creada.data['id']).update(especificacion={'sql': 'select * from usuario'})
        self.assertEqual(client.post('/api/reportes/qbe/previsualizar/', {'definicion_id': creada.data['id']}, format='json').status_code, 400)

    def test_error_sanitizado_y_no_escritura_de_fuentes(self):
        client = self.cliente(self.director)
        creada = self.crear(client)
        with patch('aplicaciones.reportes.views.ejecutar_qbe', side_effect=ValueError('password token sql')):
            respuesta = client.post('/api/reportes/qbe/previsualizar/', {'definicion_id': creada.data['id']}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        ejecucion = EjecucionReporte.objects.get(pk=respuesta.data['ejecucion_id'])
        self.assertEqual(ejecucion.error_sanitizado, 'ERROR_QBE')

    def test_exportacion_qbe_csv_reutiliza_descarga_controlada(self):
        client = self.cliente(self.director)
        creada = self.crear(client)
        respuesta = client.post('/api/reportes/qbe/exportar/', {'definicion_id': creada.data['id'], 'formato': 'CSV'}, format='json')
        self.assertEqual(respuesta.status_code, 200, respuesta.content[:200])
        self.assertTrue(respuesta.content.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(EjecucionReporte.objects.get(pk=respuesta['X-Reporte-Ejecucion']).tipo, 'QBE')

    def test_actualiza_definicion_qbe_existente(self):
        client = self.cliente(self.director)
        creada = self.crear(client)
        especificacion = self.spec({'campo': 'curso', 'operador': 'eq', 'valor': self.course.pk})
        respuesta = client.patch(
            f"/api/reportes/qbe/definiciones/{creada.data['id']}/", {'especificacion': especificacion}, format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['especificacion']['condiciones']['valor'], self.course.pk)

    def test_grupos_orden_y_previsualizacion_sin_guardar(self):
        client = self.cliente(self.director)
        condicion = {'id': 'c1', 'campo': 'curso', 'operador': 'eq', 'valor': self.course.pk}
        anidada = {'id': 'g1', 'logica': 'OR', 'condiciones': [
            {'id': 'c2', 'campo': 'activo', 'operador': 'eq', 'valor': True},
            {'id': 'c3', 'campo': 'curso', 'operador': 'eq', 'valor': self.course.pk + 1000},
        ]}
        spec = {**self.spec({'logica': 'AND', 'condiciones': [condicion, anidada]}), 'orden': [{'campo': 'curso', 'direccion': 'asc'}], 'limite': 5}
        respuesta = client.post('/api/reportes/qbe/previsualizar/', {'codigo_fuente': 'ESTUDIANTES_INSCRITOS', 'especificacion': spec}, format='json')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['cantidad'], 1)
        self.assertEqual(respuesta.data['limite'], 5)
        self.assertEqual(respuesta.data['orden'], spec['orden'])
        spec['condiciones']['logica'] = 'OR'
        self.assertEqual(client.post('/api/reportes/qbe/previsualizar/', {'codigo_fuente': 'ESTUDIANTES_INSCRITOS', 'especificacion': spec}, format='json').status_code, 200)
        self.assertFalse(ReporteDefinicion.objects.filter(propietario=self.director).exists())

    def test_ids_invalidos_y_archivo_definicion(self):
        client = self.cliente(self.director)
        spec = self.spec({'logica': 'AND', 'condiciones': [{'id': 'mal-campo', 'campo': 'curso__id', 'operador': 'eq', 'valor': 1}]})
        respuesta = self.crear(client, especificacion=spec)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('mal-campo', str(respuesta.data))
        creada = self.crear(client)
        pk = creada.data['id']
        self.assertEqual(client.get(f'/api/reportes/qbe/definiciones/{pk}/').status_code, 200)
        self.assertEqual(client.post(f'/api/reportes/qbe/definiciones/{pk}/archivar/', {}, format='json').status_code, 200)
        self.assertEqual(client.post('/api/reportes/qbe/previsualizar/', {'definicion_id': pk}, format='json').status_code, 404)

    def test_exportacion_historial_y_auditoria_sanitizada(self):
        client = self.cliente(self.director)
        spec = self.spec({'id': 'c-segura', 'campo': 'curso', 'operador': 'eq', 'valor': self.course.pk})
        creada = self.crear(client, especificacion=spec)
        for formato in ('CSV', 'PDF'):
            respuesta = client.post('/api/reportes/qbe/exportar/', {'definicion_id': creada.data['id'], 'formato': formato}, format='json')
            self.assertEqual(respuesta.status_code, 200)
            ejecucion = EjecucionReporte.objects.get(pk=respuesta['X-Reporte-Ejecucion'])
            self.assertIsNotNone(ejecucion.archivo_referencia)
            auditoria = EventoAuditoria.objects.filter(entidad='REPORTE_EJECUCION', entidad_id=str(ejecucion.pk), accion='EXPORTAR').get()
            self.assertNotIn(ejecucion.archivo_referencia, str(auditoria.cambios_sanitizados))
            self.assertNotIn('valor', str(auditoria.cambios_sanitizados))
            self.assertIn('formato:' + formato, auditoria.cambios_sanitizados['campos'])
        historial = client.get('/api/reportes/ejecuciones/')
        self.assertEqual(historial.status_code, 200)
        self.assertEqual(historial.data['count'], 2)

    def test_secretaria_con_permiso_explicito_y_definicion_ajena(self):
        puesto, _ = Puesto.objects.get_or_create(nombre='Secretaria')
        self.regent.admin.puesto = puesto
        self.regent.admin.save()
        secretaria = self.cliente(self.regent)
        self.assertEqual(secretaria.get('/api/reportes/qbe/catalogo/').status_code, 403)
        for recurso, acciones in {'reporte-qbe': ('validar', 'ejecutar'), 'reporte-definicion': ('crear',)}.items():
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=recurso)
            for nombre in acciones:
                accion, _ = Accion.objects.get_or_create(nombre=nombre)
                PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=accion)
        creada = self.crear(secretaria)
        self.assertEqual(creada.status_code, 201, creada.data)
        self.assertEqual(creada.data['unidad_educativa'], self.unit.pk)
        self.assertEqual(secretaria.post('/api/reportes/qbe/previsualizar/', {'definicion_id': creada.data['id']}, format='json').status_code, 200)
        self.assertEqual(self.cliente(self.outsider).get(f"/api/reportes/qbe/definiciones/{creada.data['id']}/").status_code, 404)

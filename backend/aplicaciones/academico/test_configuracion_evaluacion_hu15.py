from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from aplicaciones.calendario.models import CalendarioAcademico
from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.usuarios.models import Admin, EventoAuditoria, Puesto, Rol, Usuario

from .models import ConfiguracionEvaluacion, DimensionEvaluacion


class ConfiguracionEvaluacionHU15Tests(APITestCase):
    url = '/api/academico/configuraciones-evaluacion/'
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio_a = Colegio.objects.create(nombre='Colegio A HU15', direccion='A', telefono='1')
        cls.colegio_b = Colegio.objects.create(nombre='Colegio B HU15', direccion='B', telefono='2')
        cls.ua = UnidadEducativa.objects.create(
            codigo_sie='HU15-UA', turno='TARDE', nombre='HU15-UA', colegio=cls.colegio_a,
        )
        cls.ub = UnidadEducativa.objects.create(
            codigo_sie='HU15-UB', turno='TARDE', nombre='HU15-UB', colegio=cls.colegio_b,
        )
        # La gestión se crea aquí, lo que dispara la señal de HU-15 y ya
        # debería dejar sembrada la configuración + 5 dimensiones oficiales.
        cls.gestion_a = CalendarioAcademico.objects.create(
            unidad_educativa=cls.ua, año=2026, fecha_inicio=date(2026, 2, 1),
            fecha_fin=date(2026, 11, 30), activo=True,
        )
        cls.gestion_b = CalendarioAcademico.objects.create(
            unidad_educativa=cls.ub, año=2026, fecha_inicio=date(2026, 2, 1),
            fecha_fin=date(2026, 11, 30), activo=True,
        )

        cls.superusuario = Usuario.objects.create_superuser(
            ci='HU15-SUP', email='hu15-sup@example.com', nombre='Super', apellido='HU15',
            username='hu15_sup', fecha_nacimiento='1990-01-01', password=cls.password,
        )
        rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        cls.director = cls._admin('DIR', cls.ua, rol_admin, 'Director')
        cls.director_b = cls._admin('DIRB', cls.ub, rol_admin, 'Director')
        cls.profesor = cls._usuario('PRF', cls.ua, rol_profesor)

    @classmethod
    def _usuario(cls, sufijo, unidad, rol):
        return Usuario.objects.create_user(
            ci=f'HU15-{sufijo}', email=f'hu15-{sufijo.lower()}@example.com',
            nombre=sufijo, apellido='HU15', username=f'hu15_{sufijo.lower()}',
            fecha_nacimiento='1990-01-01', password=cls.password, rol=rol, unidad=unidad,
        )

    @classmethod
    def _admin(cls, sufijo, unidad, rol, puesto):
        usuario = cls._usuario(sufijo, unidad, rol)
        cargo, _ = Puesto.objects.get_or_create(nombre=puesto)
        Admin.objects.create(usuario=usuario, unidad=unidad, puesto=cargo)
        return usuario

    def autenticar(self, usuario=None):
        self.client.force_authenticate(usuario or self.superusuario)

    def payload_configurar(self, **cambios):
        data = {
            'calendario_academico': self.gestion_a.pk,
            'nivel': 'PRI',
            'nota_minima': '0', 'nota_maxima': '100', 'nota_aprobacion': '51', 'decimales': 0,
            'regla_redondeo': 'NORMAL',
            'dimensiones': [
                {'codigo': 'SER', 'nombre': 'Ser', 'ponderacion': '10', 'orden': 1},
                {'codigo': 'SABER', 'nombre': 'Saber', 'ponderacion': '35', 'orden': 2},
                {'codigo': 'HACER', 'nombre': 'Hacer', 'ponderacion': '35', 'orden': 3},
                {'codigo': 'DECIDIR', 'nombre': 'Decidir', 'ponderacion': '10', 'orden': 4},
                {'codigo': 'AUTOEVAL', 'nombre': 'Autoevaluación', 'ponderacion': '10', 'orden': 5},
            ],
        }
        data.update(cambios)
        return data

    # --- Auto-seed al crear la gestión académica (HU-15) ---

    def test_crear_gestion_siembra_configuracion_y_dimensiones_oficiales(self):
        for nivel in ('PRI', 'SEC'):
            configuracion = ConfiguracionEvaluacion.objects.get(
                calendario_academico=self.gestion_a, nivel=nivel,
            )
            self.assertEqual(configuracion.nota_aprobacion, Decimal('51.00'))
            ponderaciones = list(
                configuracion.dimensiones.order_by('orden').values_list('codigo', 'ponderacion'),
            )
            self.assertEqual(
                ponderaciones,
                [
                    ('SER', Decimal('10.00')), ('SABER', Decimal('35.00')),
                    ('HACER', Decimal('35.00')), ('DECIDIR', Decimal('10.00')),
                    ('AUTOEVAL', Decimal('10.00')),
                ],
            )

    def test_crear_gestion_no_siembra_nivel_inicial(self):
        self.assertFalse(
            ConfiguracionEvaluacion.objects.filter(
                calendario_academico=self.gestion_a, nivel='INI',
            ).exists(),
        )

    # --- Endpoint de configuración masiva ---

    def test_configurar_exige_suma_de_ponderaciones_igual_a_100(self):
        self.autenticar(self.director)
        payload = self.payload_configurar()
        payload['dimensiones'][0]['ponderacion'] = '20'  # rompe la suma = 100
        response = self.client.put(f'{self.url}configurar/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('dimensiones', response.data)

    def test_configurar_exige_exactamente_5_dimensiones(self):
        self.autenticar(self.director)
        payload = self.payload_configurar()
        payload['dimensiones'] = payload['dimensiones'][:4]
        response = self.client.put(f'{self.url}configurar/', payload, format='json')
        self.assertEqual(response.status_code, 400)

    def test_configurar_valida_nota_aprobacion_dentro_de_rango(self):
        self.autenticar(self.director)
        payload = self.payload_configurar(nota_aprobacion='150')
        response = self.client.put(f'{self.url}configurar/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('nota_aprobacion', response.data)

    def test_director_puede_reconfigurar_dimensiones_de_su_unidad(self):
        self.autenticar(self.director)
        payload = self.payload_configurar(nota_aprobacion='55')
        response = self.client.put(f'{self.url}configurar/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['nota_aprobacion'], '55.00')
        self.assertEqual(len(response.data['dimensiones']), 5)
        self.assertTrue(
            EventoAuditoria.objects.filter(entidad='CONFIGURACION_EVALUACION').exists(),
        )

    def test_reconfigurar_es_idempotente_no_duplica_dimensiones(self):
        self.autenticar(self.director)
        self.client.put(f'{self.url}configurar/', self.payload_configurar(), format='json')
        self.client.put(f'{self.url}configurar/', self.payload_configurar(), format='json')
        configuracion = ConfiguracionEvaluacion.objects.get(
            calendario_academico=self.gestion_a, nivel='PRI',
        )
        self.assertEqual(configuracion.dimensiones.count(), 5)

    def test_director_no_puede_configurar_otra_unidad_educativa(self):
        self.autenticar(self.director)
        payload = self.payload_configurar(calendario_academico=self.gestion_b.pk)
        response = self.client.put(f'{self.url}configurar/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('calendario_academico', response.data)

    def test_profesor_no_puede_configurar(self):
        self.autenticar(self.profesor)
        response = self.client.put(f'{self.url}configurar/', self.payload_configurar(), format='json')
        self.assertEqual(response.status_code, 403)

    def test_anonimo_no_puede_listar(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_director_solo_ve_configuraciones_de_su_unidad(self):
        self.autenticar(self.director)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        unidades = {item['unidad_educativa'] for item in response.data['results']} \
            if isinstance(response.data, dict) and 'results' in response.data \
            else {item['unidad_educativa'] for item in response.data}
        self.assertEqual(unidades, {self.ua.pk})

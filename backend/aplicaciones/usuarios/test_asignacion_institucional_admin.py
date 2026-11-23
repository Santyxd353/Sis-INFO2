from rest_framework import status
from rest_framework.test import APITestCase

from aplicaciones.institucion.models import Colegio, UnidadEducativa

from .models import Accion, Admin, ModeloPermitido, PermisoPuesto, Puesto, Rol, Usuario
from .tenancy import ErrorAlcanceInstitucional, resolver_alcance


class AsignacionInstitucionalAdminTests(APITestCase):
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio_a = Colegio.objects.create(
            nombre='Satélite Norte', direccion='Dirección A', telefono='70000001',
        )
        cls.colegio_b = Colegio.objects.create(
            nombre='Colegio B', direccion='Dirección B', telefono='70000002',
        )
        cls.unidad_a1 = cls._unidad('ADM-A1', 'Módulo Primaria', cls.colegio_a)
        cls.unidad_a2 = cls._unidad('ADM-A2', 'Módulo Secundaria', cls.colegio_a)
        cls.unidad_b1 = cls._unidad('ADM-B1', 'Unidad B', cls.colegio_b)
        cls.rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        cls.director, _ = Puesto.objects.get_or_create(nombre='Director')
        listar, _ = Accion.objects.get_or_create(nombre='listar')
        modelo_unidad, _ = ModeloPermitido.objects.get_or_create(
            nombre='unidad-educativa',
        )
        PermisoPuesto.objects.get_or_create(
            puesto=cls.director, modelo=modelo_unidad, accion=listar,
        )
        cls.secretaria, _ = Puesto.objects.get_or_create(nombre='Secretaría')
        cls.superusuario = Usuario.objects.create_superuser(
            ci='ADM-SUP', email='adm-sup@example.com', nombre='Super', apellido='Admin',
            username='adm_sup', password=cls.password,
        )

    @classmethod
    def _unidad(cls, codigo, nombre, colegio):
        return UnidadEducativa.objects.create(
            codigo_sie=codigo, turno='TARDE', nombre=nombre, colegio=colegio,
        )

    def setUp(self):
        self.client.force_authenticate(self.superusuario)

    def _payload(self, codigo, puesto, colegio, unidad_marker='omitida'):
        payload = {
            'ci': f'ADM-{codigo}', 'username': f'adm_{codigo.lower()}',
            'email': f'adm-{codigo.lower()}@example.com', 'nombre': codigo,
            'apellido': 'Institucional', 'sexo': 'F', 'password': self.password,
            'rol_id': self.rol_admin.pk, 'puesto_id': puesto.pk,
            'colegio_id': colegio.pk,
        }
        if unidad_marker != 'omitida':
            payload['unidad_id'] = unidad_marker.pk if unidad_marker else None
        return payload

    def _crear(self, codigo, puesto, colegio, unidad_marker='omitida'):
        return self.client.post(
            '/api/usuarios/usuarios/',
            self._payload(codigo, puesto, colegio, unidad_marker),
            format='json',
        )

    def test_crea_director_con_colegio_sin_seleccionar_unidad(self):
        response = self._crear('DIR', self.director, self.colegio_a)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        usuario = Usuario.objects.get(pk=response.data['id'])
        self.assertIsNone(usuario.unidad_id)
        self.assertIsNone(usuario.admin.unidad_id)
        self.assertEqual(usuario.admin.colegio_id, self.colegio_a.pk)

    def test_director_recibe_alcance_colegio_y_accede_solo_a_sus_unidades(self):
        response = self._crear('DIRSCOPE', self.director, self.colegio_a)
        usuario = Usuario.objects.get(pk=response.data['id'])
        self.client.force_authenticate(usuario)
        perfil = self.client.get('/api/usuarios/perfil/')
        self.assertEqual(perfil.data['alcance'], {
            'tipo': 'COLEGIO', 'colegio_id': self.colegio_a.pk,
            'unidad_id': None, 'colegio_nombre': self.colegio_a.nombre,
            'unidad_nombre': None,
        })
        unidades = self.client.get('/api/institucion/unidades-educativas/')
        self.assertEqual(unidades.status_code, status.HTTP_200_OK, unidades.data)
        self.assertIn('count', unidades.data)
        self.assertIn('next', unidades.data)
        self.assertIn('previous', unidades.data)
        self.assertIn('results', unidades.data)
        ids_unidades = {item['id'] for item in unidades.data['results']}
        self.assertEqual(ids_unidades, {self.unidad_a1.pk, self.unidad_a2.pk})
        self.assertNotIn(self.unidad_b1.pk, ids_unidades)
        self.assertEqual(
            self.client.get(
                '/api/institucion/unidades-educativas/', {'colegio': self.colegio_a.pk},
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get(
                '/api/institucion/unidades-educativas/', {'colegio': self.colegio_b.pk},
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_rechaza_director_con_colegio_inactivo(self):
        self.colegio_b.estado = Colegio.Estado.INACTIVO
        self.colegio_b.save(update_fields=['estado'])
        response = self._crear('DIRINACT', self.director, self.colegio_b)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('colegio_id', response.data)

    def test_crea_secretaria_con_colegio_y_unidad_coherentes(self):
        response = self._crear('SEC', self.secretaria, self.colegio_a, self.unidad_a1)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        usuario = Usuario.objects.get(pk=response.data['id'])
        self.assertEqual(usuario.unidad_id, self.unidad_a1.pk)
        self.assertEqual(usuario.admin.unidad_id, self.unidad_a1.pk)
        self.assertEqual(usuario.admin.colegio_id, self.colegio_a.pk)
        self.assertEqual(response.data['alcance'], {
            'tipo': 'UNIDAD', 'colegio_id': self.colegio_a.pk,
            'unidad_id': self.unidad_a1.pk, 'colegio_nombre': self.colegio_a.nombre,
            'unidad_nombre': self.unidad_a1.nombre,
        })

    def test_rechaza_secretaria_sin_unidad(self):
        response = self._crear('SECNULL', self.secretaria, self.colegio_a, None)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('unidad_id', response.data)

    def test_rechaza_secretaria_con_unidad_de_otro_colegio(self):
        response = self._crear('SECAJENA', self.secretaria, self.colegio_a, self.unidad_b1)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('unidad_id', response.data)

    def test_edita_secretaria_y_sincroniza_ambas_unidades(self):
        response = self._crear('SECEDIT', self.secretaria, self.colegio_a, self.unidad_a1)
        usuario_id = response.data['id']
        response = self.client.patch(
            f'/api/usuarios/usuarios/{usuario_id}/',
            {'colegio_id': self.colegio_a.pk, 'unidad_id': self.unidad_a2.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        usuario = Usuario.objects.get(pk=usuario_id)
        self.assertEqual(usuario.unidad_id, self.unidad_a2.pk)
        self.assertEqual(usuario.admin.unidad_id, self.unidad_a2.pk)

    def test_cambia_secretaria_a_director_sin_elegir_otra_unidad(self):
        response = self._crear('SECTODIR', self.secretaria, self.colegio_a, self.unidad_a1)
        usuario_id = response.data['id']
        response = self.client.patch(
            f'/api/usuarios/usuarios/{usuario_id}/',
            {'puesto_id': self.director.pk, 'colegio_id': self.colegio_a.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        usuario = Usuario.objects.get(pk=usuario_id)
        self.assertEqual(resolver_alcance(usuario)['tipo'], 'COLEGIO')
        self.assertEqual(usuario.unidad_id, self.unidad_a1.pk)

    def test_cambiar_director_a_secretaria_exige_unidad(self):
        response = self._crear('DIRTOSEC', self.director, self.colegio_a)
        response = self.client.patch(
            f"/api/usuarios/usuarios/{response.data['id']}/",
            {'puesto_id': self.secretaria.pk, 'colegio_id': self.colegio_a.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('unidad_id', response.data)

    def test_director_heredado_conserva_fallback_temporal(self):
        usuario = Usuario.objects.create_user(
            ci='ADM-LEG', email='adm-leg@example.com', nombre='Legacy', apellido='Director',
            username='adm_legacy', password=self.password, rol=self.rol_admin,
            unidad=self.unidad_a1,
        )
        Admin.objects.create(usuario=usuario, puesto=self.director, unidad=self.unidad_a1)
        self.assertEqual(resolver_alcance(usuario), {
            'tipo': 'COLEGIO', 'colegio_id': self.colegio_a.pk, 'unidad_id': None,
        })

    def test_divergencias_de_director_y_secretaria_se_rechazan(self):
        director = Usuario.objects.create_user(
            ci='ADM-DIV-D', email='adm-div-d@example.com', nombre='D', apellido='D',
            username='adm_div_d', password=self.password, rol=self.rol_admin,
            unidad=self.unidad_a1,
        )
        Admin.objects.create(
            usuario=director, puesto=self.director, unidad=self.unidad_a1, colegio=self.colegio_b,
        )
        secretaria = Usuario.objects.create_user(
            ci='ADM-DIV-S', email='adm-div-s@example.com', nombre='S', apellido='S',
            username='adm_div_s', password=self.password, rol=self.rol_admin,
            unidad=self.unidad_a1,
        )
        Admin.objects.create(
            usuario=secretaria, puesto=self.secretaria, unidad=self.unidad_a1,
            colegio=self.colegio_b,
        )
        with self.assertRaises(ErrorAlcanceInstitucional):
            resolver_alcance(director)
        with self.assertRaises(ErrorAlcanceInstitucional):
            resolver_alcance(secretaria)

    def test_superadmin_filtra_unidades_por_colegio_y_valida_parametro(self):
        response = self.client.get(
            '/api/institucion/unidades-educativas/', {'colegio': self.colegio_a.pk},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item['id'] for item in response.data['results']},
            {self.unidad_a1.pk, self.unidad_a2.pk},
        )
        for invalido in ('abc', '0', '-1'):
            response = self.client.get('/api/institucion/unidades-educativas/', {'colegio': invalido})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_perfil_conserva_jwt_y_expone_asignacion_institucional(self):
        response = self._crear('JWT', self.director, self.colegio_a)
        usuario = Usuario.objects.get(pk=response.data['id'])
        login = self.client.post(
            '/api/usuarios/login/', {'username': usuario.username, 'password': self.password},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK, login.data)
        self.assertIn('access', login.data)
        self.assertIn('refresh', login.data)
        self.assertEqual(login.data['user']['colegio']['id'], self.colegio_a.pk)

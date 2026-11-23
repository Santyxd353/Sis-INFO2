from rest_framework import status
from rest_framework.test import APITestCase

from aplicaciones.institucion.models import Colegio, UnidadEducativa

from .models import (
    Accion, Admin, ModeloPermitido, PermisoComponente, PermisoPuesto,
    PermisoRol, Puesto, Rol, Usuario,
)
from rest_framework.exceptions import PermissionDenied

from .privilegios import permisos_funcionales, permisos_ui, roles_efectivos
from .tenancy import ErrorAlcanceInstitucional, resolver_alcance, validar_unidad


class AlcanceInstitucionalTests(APITestCase):
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio_a = Colegio.objects.create(nombre='Colegio alcance A')
        cls.colegio_b = Colegio.objects.create(nombre='Colegio alcance B')
        cls.a1 = cls._unidad('ALC-A1', cls.colegio_a)
        cls.a2 = cls._unidad('ALC-A2', cls.colegio_a)
        cls.b1 = cls._unidad('ALC-B1', cls.colegio_b)
        cls.rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        cls.rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        cls.puesto_director, _ = Puesto.objects.get_or_create(nombre='Director')
        cls.puesto_secretaria, _ = Puesto.objects.get_or_create(nombre='Secretaría')
        cls.director = cls._admin('DIR', cls.a1, cls.puesto_director)
        cls.secretaria = cls._admin('SEC', cls.a1, cls.puesto_secretaria)
        cls.puesto_tesoreria, _ = Puesto.objects.get_or_create(nombre='Tesorería')
        cls.puesto_admin_generico, _ = Puesto.objects.get_or_create(nombre='Administrador Institucional')
        cls.tesoreria_colegio = cls._tesoreria('TES-COLEGIO', cls.colegio_a)
        cls.tesoreria_unidad = cls._tesoreria('TES-UNIDAD', cls.colegio_a, cls.a1)
        cls.admin_generico = cls._tesoreria('ADMIN-GENERICO', cls.colegio_a, cls.a1, cls.puesto_admin_generico)
        cls.profesor = cls._usuario('PROF', cls.a1, cls.rol_profesor)
        cls.usuario_a2 = cls._usuario('A2', cls.a2, cls.rol_profesor)
        cls.usuario_b1 = cls._usuario('B1', cls.b1, cls.rol_profesor)
        cls.superusuario = Usuario.objects.create_superuser(
            ci='ALC-SUP', email='alc-sup@example.com', nombre='Super', apellido='Alcance',
            username='alc_sup', password=cls.password,
        )
        listar, _ = Accion.objects.get_or_create(nombre='listar')
        modelo_usuario, _ = ModeloPermitido.objects.get_or_create(nombre='usuario')
        modelo_unidad, _ = ModeloPermitido.objects.get_or_create(nombre='unidad-educativa')
        for puesto in (cls.puesto_director, cls.puesto_secretaria):
            for modelo in (modelo_usuario, modelo_unidad):
                PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo, accion=listar)

    @classmethod
    def _unidad(cls, codigo, colegio):
        return UnidadEducativa.objects.create(
            colegio=colegio, codigo_sie=codigo, turno='TARDE', nombre=codigo,
        )

    @classmethod
    def _usuario(cls, codigo, unidad, rol):
        return Usuario.objects.create_user(
            ci=f'ALC-{codigo}', email=f'alc-{codigo.lower()}@example.com',
            nombre=codigo, apellido='Alcance', username=f'alc_{codigo.lower()}',
            password=cls.password, rol=rol, unidad=unidad,
        )

    @classmethod
    def _admin(cls, codigo, unidad, puesto):
        usuario = cls._usuario(codigo, unidad, cls.rol_admin)
        Admin.objects.create(usuario=usuario, unidad=unidad, colegio=unidad.colegio, puesto=puesto)
        return usuario

    @classmethod
    def _tesoreria(cls, codigo, colegio, unidad=None, puesto=None):
        usuario = Usuario.objects.create_user(
            ci=f'ALC-{codigo}', email=f'alc-{codigo.lower()}@example.com',
            nombre=codigo, apellido='Alcance', username=f'alc_{codigo.lower()}',
            password=cls.password, rol=cls.rol_admin, unidad=unidad,
        )
        Admin.objects.create(
            usuario=usuario, unidad=unidad, colegio=colegio,
            puesto=puesto or cls.puesto_tesoreria,
        )
        return usuario

    def test_resolvedor_define_los_cuatro_alcances(self):
        self.assertEqual(resolver_alcance(self.superusuario)['tipo'], 'GLOBAL')
        self.assertEqual(resolver_alcance(self.director)['tipo'], 'COLEGIO')
        self.assertEqual(resolver_alcance(self.secretaria)['tipo'], 'UNIDAD')
        self.assertEqual(resolver_alcance(self.profesor)['tipo'], 'PERSONAL')

    def test_director_lista_unidades_y_usuarios_de_su_colegio(self):
        self.client.force_authenticate(self.director)
        unidades = self.client.get('/api/institucion/unidades-educativas/')
        self.assertEqual({item['id'] for item in unidades.data['results']}, {self.a1.pk, self.a2.pk})
        usuarios = self.client.get('/api/usuarios/usuarios/')
        self.assertEqual(
            {item['id'] for item in usuarios.data},
            {self.director.pk, self.secretaria.pk, self.profesor.pk, self.usuario_a2.pk,
             self.tesoreria_colegio.pk, self.tesoreria_unidad.pk, self.admin_generico.pk},
        )

    def test_secretaria_solo_lista_su_unidad_y_sus_usuarios(self):
        self.client.force_authenticate(self.secretaria)
        unidades = self.client.get('/api/institucion/unidades-educativas/')
        self.assertEqual([item['id'] for item in unidades.data['results']], [self.a1.pk])
        usuarios = self.client.get('/api/usuarios/usuarios/')
        self.assertEqual(
            {item['id'] for item in usuarios.data},
            {self.director.pk, self.secretaria.pk, self.profesor.pk,
             self.tesoreria_unidad.pk, self.admin_generico.pk},
        )

    def test_filtros_y_detalles_no_amplian_el_alcance(self):
        self.client.force_authenticate(self.secretaria)
        self.assertEqual(
            self.client.get(f'/api/institucion/unidades-educativas/{self.a2.pk}/').status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f'/api/usuarios/usuarios/{self.usuario_b1.pk}/').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_perfil_expone_alcance_y_permisos_efectivos(self):
        self.client.force_authenticate(self.director)
        response = self.client.get('/api/usuarios/perfil/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['alcance'], {
            'tipo': 'COLEGIO', 'colegio_id': self.colegio_a.pk,
            'unidad_id': None, 'colegio_nombre': self.colegio_a.nombre,
            'unidad_nombre': None,
        })
        self.assertIn(
            {'modelo': 'usuario', 'accion': 'listar'}, response.data['permisos_efectivos'],
        )

    def test_divergencia_entre_usuario_y_admin_se_detecta(self):
        self.director.admin.unidad = self.a2
        self.director.admin.save(update_fields=['unidad'])
        with self.assertRaises(ErrorAlcanceInstitucional):
            resolver_alcance(self.director)

    def test_unidad_sin_colegio_se_rechaza_de_forma_controlada(self):
        huerfana = self._unidad('ALC-H', None)
        usuario = self._admin('H', huerfana, self.puesto_secretaria)
        self.client.force_authenticate(usuario)
        response = self.client.get('/api/institucion/unidades-educativas/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tesoreria_resuelve_alcance_de_colegio_y_unidad_sin_permisos_implicitos(self):
        colegio = resolver_alcance(self.tesoreria_colegio)
        unidad = resolver_alcance(self.tesoreria_unidad)
        self.assertEqual((colegio['tipo'], colegio['colegio_id'], colegio['unidad_id']),
                         ('COLEGIO', self.colegio_a.pk, None))
        self.assertEqual((unidad['tipo'], unidad['colegio_id'], unidad['unidad_id']),
                         ('UNIDAD', self.colegio_a.pk, self.a1.pk))
        from .models import PermisoPuesto
        self.assertFalse(PermisoPuesto.objects.filter(puesto=self.puesto_tesoreria).exists())
        from .privilegios import permisos_funcionales
        self.assertNotIn(('usuario', 'listar'), permisos_funcionales(self.tesoreria_colegio) or set())

    def test_rol_funcional_y_componentes_se_aplican_por_puesto_y_alcance(self):
        modelo_usuario, _ = ModeloPermitido.objects.get_or_create(nombre='usuario')
        accion_listar, _ = Accion.objects.get_or_create(nombre='listar')
        rol_colegio = Rol.objects.create(
            nombre='Tesorería Colegio Alfa', colegio=self.colegio_a,
            puesto=self.puesto_tesoreria, categoria=Rol.Categoria.FUNCIONAL,
        )
        PermisoRol.objects.create(rol=rol_colegio, modelo=modelo_usuario, accion=accion_listar)
        self.assertIn(rol_colegio, roles_efectivos(self.tesoreria_colegio))
        self.assertIn(rol_colegio, roles_efectivos(self.tesoreria_unidad))
        self.assertNotIn(rol_colegio, roles_efectivos(self._tesoreria(
            'TES-OTRO-COLEGIO', self.colegio_b, self.b1,
        )))
        self.assertIn(('usuario', 'listar'), permisos_funcionales(self.tesoreria_colegio))

        rol_unidad = Rol.objects.create(
            nombre='Tesorería Unidad Alfa', colegio=self.colegio_a,
            unidad_educativa=self.a1, puesto=self.puesto_tesoreria,
            categoria=Rol.Categoria.FUNCIONAL,
        )
        PermisoComponente.objects.create(
            rol=rol_unidad, componente='modulo:tesoreria', visible=True, editable=True,
        )
        self.assertIn(rol_unidad, roles_efectivos(self.tesoreria_unidad))
        self.assertNotIn(rol_unidad, roles_efectivos(self.tesoreria_colegio))
        self.assertEqual(
            next(item for item in permisos_ui(self.tesoreria_unidad)
                 if item['componente'] == 'modulo:tesoreria'),
            {'componente': 'modulo:tesoreria', 'visible': True, 'editable': True},
        )

    def test_tesoreria_aisla_colegio_y_unidad(self):
        validar_unidad(self.tesoreria_colegio, self.a1)
        validar_unidad(self.tesoreria_colegio, self.a2)
        with self.assertRaises(PermissionDenied):
            validar_unidad(self.tesoreria_colegio, self.b1)
        validar_unidad(self.tesoreria_unidad, self.a1)
        with self.assertRaises(PermissionDenied):
            validar_unidad(self.tesoreria_unidad, self.a2)

    def test_director_secretaria_y_admin_generico_conservan_sus_alcances(self):
        self.assertEqual(resolver_alcance(self.director)['tipo'], 'COLEGIO')
        self.assertEqual(resolver_alcance(self.secretaria)['tipo'], 'UNIDAD')
        self.assertEqual(resolver_alcance(self.admin_generico)['tipo'], 'UNIDAD')
        self.assertEqual(resolver_alcance(self.admin_generico)['unidad_id'], self.a1.pk)
        admin_sin_unidad = self._tesoreria(
            'ADMIN-SIN-UNIDAD', self.colegio_a, puesto=self.puesto_admin_generico,
        )
        with self.assertRaises(ErrorAlcanceInstitucional):
            resolver_alcance(admin_sin_unidad)

    def test_perfil_autenticado_expone_puesto_y_alcance_de_tesoreria(self):
        self.client.force_authenticate(self.tesoreria_colegio)
        respuesta = self.client.get('/api/usuarios/perfil/')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['perfil']['puesto']['nombre'], 'Tesorería')
        self.assertEqual(respuesta.data['alcance']['tipo'], 'COLEGIO')

    def test_serializer_acepta_tesoreria_sin_unidad_y_exige_colegio(self):
        from types import SimpleNamespace
        from .serializer import UsuarioSerializer

        base = {
            'ci': 'ALC-TES-NUEVO', 'username': 'alc_tes_nuevo',
            'email': 'alc-tes-nuevo@example.com', 'nombre': 'Tesoreria',
            'apellido': 'Nueva', 'fecha_nacimiento': '1990-01-01', 'sexo': 'F',
            'rol_id': self.rol_admin.pk, 'puesto_id': self.puesto_tesoreria.pk,
            'colegio_id': self.colegio_a.pk, 'unidad_id': None,
            'password': self.password,
        }
        serializer = UsuarioSerializer(
            data=base, context={'request': SimpleNamespace(user=self.director)},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        sin_colegio = {**base, 'ci': 'ALC-TES-SIN-COLEGIO', 'username': 'alc_tes_sin_colegio',
                       'email': 'alc-tes-sin-colegio@example.com'}
        sin_colegio.pop('colegio_id')
        serializer = UsuarioSerializer(
            data=sin_colegio, context={'request': SimpleNamespace(user=self.director)},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('colegio_id', serializer.errors)


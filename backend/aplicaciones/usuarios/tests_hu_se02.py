"""Tests HU-SE02: administrar usuarios, roles y privilegios granulares."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from aplicaciones.institucion.models import Colegio, UnidadEducativa

from .models import (
    Accion, ModeloPermitido, PermisoComponente, PermisoRol, Puesto, Rol,
    Usuario,
)
from .privilegios import (
    categoria_usuario, permisos_funcionales, permisos_ui, puede,
    puede_componente, puede_editar_componente, roles_efectivos,
)
from .permissions import PermisoPorRol


class BaseHUSe02(APITestCase):
    """Fixtures: dos colegios, superadmin, directores por colegio y un profesor."""

    @classmethod
    def setUpTestData(cls):
        cls.colegio_a = Colegio.objects.create(nombre='Colegio Alfa', direccion='A', telefono='1')
        cls.unidad_a = UnidadEducativa.objects.create(
            codigo_sie='SE02-UA', turno='MANANA', nombre='Unidad Alfa', colegio=cls.colegio_a,
        )
        cls.colegio_b = Colegio.objects.create(nombre='Colegio Beta', direccion='B', telefono='2')
        cls.unidad_b = UnidadEducativa.objects.create(
            codigo_sie='SE02-UB', turno='MANANA', nombre='Unidad Beta', colegio=cls.colegio_b,
        )

        rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        cls.rol_admin = rol_admin
        cls.rol_profesor = rol_profesor
        cls.puesto_director, _ = Puesto.objects.get_or_create(nombre='Director')

        cls.superadmin = Usuario.objects.create_superuser(
            ci='SE02-SUP', email='se02-sup@example.com', nombre='Super', apellido='Admin',
            username='se02_sup', fecha_nacimiento='1980-01-01', password='Clave-Segura-123',
        )

        def crear_director(username, ci, colegio, unidad):
            usuario = Usuario.objects.create_user(
                ci=ci, email=f'{username}@example.com', nombre='Dir', apellido=colegio.nombre,
                username=username, fecha_nacimiento='1980-01-01', password='Clave-Segura-123',
                rol=rol_admin, unidad=unidad,
            )
            from .models import Admin
            Admin.objects.create(
                usuario=usuario, puesto=cls.puesto_director, unidad=unidad, colegio=colegio,
            )
            return usuario

        cls.director_a = crear_director('se02_dir_a', 'SE02-DIR-A', cls.colegio_a, cls.unidad_a)
        cls.director_b = crear_director('se02_dir_b', 'SE02-DIR-B', cls.colegio_b, cls.unidad_b)

        cls.profesor_a = Usuario.objects.create_user(
            ci='SE02-PRF-A', email='se02-prf-a@example.com', nombre='Prof', apellido='Alfa',
            username='se02_prf_a', fecha_nacimiento='1985-01-01', password='Clave-Segura-123',
            rol=rol_profesor, unidad=cls.unidad_a,
        )
        from aplicaciones.personal.models import Profesor
        Profesor.objects.create(usuario=cls.profesor_a, unidad=cls.unidad_a)

        cls.url_roles = reverse('roles-lista')
        cls.url_acciones = reverse('acciones-catalogo')
        cls.url_modelos = reverse('modelos-catalogo')

    def _crear_rol_collegiado(self, nombre='Invitado', colegio=None):
        return Rol.objects.create(
            nombre=nombre, colegio=colegio or self.colegio_a,
        )

    def _hacer_asignable(self, rol):
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='colegio')
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        PermisoRol.objects.get_or_create(rol=rol, modelo=modelo, accion=accion)
        PermisoRol.objects.get_or_create(rol=self.rol_admin, modelo=modelo, accion=accion)
        usuario_modelo, _ = ModeloPermitido.objects.get_or_create(nombre='usuario')
        editar, _ = Accion.objects.get_or_create(nombre='editar')
        PermisoRol.objects.get_or_create(rol=self.rol_admin, modelo=usuario_modelo, accion=editar)
        return rol


class CategoriasBaseTests(BaseHUSe02):
    def test_categoria_de_las_tres_categorias_base(self):
        self.assertEqual(categoria_usuario(self.superadmin), 'SUPERADMIN')
        self.assertEqual(categoria_usuario(self.director_a), 'ADMIN_COLEGIO')
        self.assertEqual(categoria_usuario(self.profesor_a), 'USUARIO_INSTITUCIONAL')

    def test_perfil_devuelve_categoria_y_alcance(self):
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.get(reverse('perfil'))
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['categoria'], 'ADMIN_COLEGIO')
        self.assertEqual(respuesta.data['alcance']['tipo'], 'COLEGIO')
        self.assertEqual(respuesta.data['alcance']['colegio_id'], self.colegio_a.pk)


class GestionDeRolesTests(BaseHUSe02):
    def test_director_crea_rol_personalizado_en_su_colegio(self):
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.post(self.url_roles, {'nombre': 'Jefe de Admision'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        rol = Rol.objects.get(pk=respuesta.data['id'])
        self.assertEqual(rol.colegio_id, self.colegio_a.pk)
        self.assertTrue(rol.activo)
        self.assertEqual(respuesta.data['categoria'], 'FUNCIONAL')
        self.assertEqual(respuesta.data['alcance'], 'COLEGIO')

    def test_director_no_puede_crear_rol_de_sistema(self):
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.post(
            self.url_roles, {'nombre': 'Coordinador', 'colegio_id': None}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_director_no_puede_crear_rol_en_otro_colegio(self):
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.post(
            self.url_roles, {'nombre': 'Intruso', 'colegio_id': self.colegio_b.pk}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_nombre_duplicado_en_el_mismo_colegio_bloqueado(self):
        self._crear_rol_collegiado('Invitado')
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.post(self.url_roles, {'nombre': 'invitado'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nombre_repetido_entre_colegios_permitido(self):
        self._crear_rol_collegiado('Delegado', colegio=self.colegio_a)
        self.client.force_authenticate(self.director_b)
        respuesta = self.client.post(self.url_roles, {'nombre': 'Delegado'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)

    def test_director_edita_y_desactiva_rol(self):
        rol = self._crear_rol_collegiado('Coordinador')
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.patch(
            reverse('rol-detalle', args=[rol.pk]), {'activo': False}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        rol.refresh_from_db()
        self.assertFalse(rol.activo)

    def test_director_elimina_rol_personalizado(self):
        rol = self._crear_rol_collegiado('Temporal')
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.delete(reverse('rol-detalle', args=[rol.pk]))
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertFalse(Rol.objects.get(pk=rol.pk).activo)

    def test_rol_sistema_no_se_puede_eliminar(self):
        self.client.force_authenticate(self.superadmin)
        rol_profesor = Rol.objects.get(nombre='Profesor')
        respuesta = self.client.delete(reverse('rol-detalle', args=[rol_profesor.pk]))
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_director_no_gestiona_roles_de_otro_colegio(self):
        rol_b = self._crear_rol_collegiado('Ajeno', colegio=self.colegio_b)
        self.client.force_authenticate(self.director_a)
        detalle = self.client.get(reverse('rol-detalle', args=[rol_b.pk]))
        self.assertEqual(detalle.status_code, status.HTTP_404_NOT_FOUND)
        respuesta = self.client.patch(
            reverse('rol-detalle', args=[rol_b.pk]), {'descripcion': 'x'}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_crea_rol_de_sistema(self):
        self.client.force_authenticate(self.superadmin)
        respuesta = self.client.post(
            self.url_roles, {'nombre': 'Auditor Global'}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(respuesta.data['categoria'], 'FUNCIONAL')
        self.assertEqual(respuesta.data['alcance'], 'SISTEMA')

    def test_roles_gestion_lista_solo_su_colegio(self):
        self._crear_rol_collegiado('Propio', colegio=self.colegio_a)
        self._crear_rol_collegiado('Ajeno', colegio=self.colegio_b)
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.get(self.url_roles, {'gestion': '1'})
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        colegios = {fila['colegio_id'] for fila in respuesta.data}
        self.assertEqual(colegios, {None, self.colegio_a.pk})

    def test_roles_asignables_solo_del_colegio(self):
        propio = self._hacer_asignable(self._crear_rol_collegiado('Asignable', colegio=self.colegio_a))
        self._crear_rol_collegiado('Ajeno', colegio=self.colegio_b)
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.get(self.url_roles, {'asignables': '1'})
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        ids = {fila['id'] for fila in respuesta.data}
        self.assertIn(propio.pk, ids)
        self.assertNotIn(Rol.objects.get(nombre='Ajeno', colegio=self.colegio_b).pk, ids)


class PermisosFuncionalesTests(BaseHUSe02):
    def _url_permisos(self, rol):
        return reverse('rol-permisos', args=[rol.pk])

    def test_admin_configura_permisos_por_modelo_y_accion(self):
        rol = self._crear_rol_collegiado('Notas')
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='colegio')
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        PermisoRol.objects.get_or_create(rol=self.rol_admin, modelo=modelo, accion=accion)
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_permisos(rol),
            {'permisos': [{'modelo': 'colegio', 'accion': 'listar'}]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['permisos'], [{'modelo': 'colegio', 'accion': 'listar'}])
        self.assertTrue(
            PermisoRol.objects.filter(
                rol=rol, modelo__nombre='colegio', accion__nombre='listar',
            ).exists(),
        )

    def test_admin_no_puede_delegar_permisos_que_no_posee(self):
        rol = self._crear_rol_collegiado('Alcance')
        ModeloPermitido.objects.get_or_create(nombre='colegio')
        self.client.force_authenticate(self.director_a)
        # Director tiene 'colegio' listar/editar pero NO eliminar.
        respuesta = self.client.put(
            self._url_permisos(rol),
            {'permisos': [
                {'modelo': 'colegio', 'accion': 'listar'},
                {'modelo': 'colegio', 'accion': 'eliminar'},
            ]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(PermisoRol.objects.filter(rol=rol).exists())

    def test_superadmin_puede_delegar_cualquier_permiso(self):
        rol = self._crear_rol_collegiado('Pleno')
        ModeloPermitido.objects.get_or_create(nombre='colegio')
        self.client.force_authenticate(self.superadmin)
        respuesta = self.client.put(
            self._url_permisos(rol),
            {'permisos': [
                {'modelo': 'colegio', 'accion': 'listar'},
                {'modelo': 'colegio', 'accion': 'eliminar'},
            ]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

    def test_accion_desconocida_rechazada(self):
        rol = self._crear_rol_collegiado('Raro')
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_permisos(rol),
            {'permisos': [{'modelo': 'estudiante', 'accion': 'volar'}]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_devuelve_403_accion_no_concedida(self):
        # Un profesor sin permiso de gestión de usuarios recibe 403 al
        # manipular la URL directamente.
        self.client.force_authenticate(self.profesor_a)
        respuesta = self.client.get(reverse('usuarios-lista'))
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_rol_adicional_concede_permiso_efectivo(self):
        rol = self._crear_rol_collegiado('Horarios')
        Modelo = ModeloPermitido.objects.create(nombre='modulo-se02')
        Accion_ = Accion.objects.get_or_create(nombre='listar')[0]
        PermisoRol.objects.create(rol=rol, modelo=Modelo, accion=Accion_)

        class Vista:
            basename = 'modulo-se02'

        class Solicitud:
            method = 'GET'
            user = self.profesor_a

        self.assertFalse(PermisoPorRol().has_permission(Solicitud(), Vista()))

        self.profesor_a.roles_extras.add(rol)
        self.profesor_a.refresh_from_db()
        self.assertTrue(PermisoPorRol().has_permission(Solicitud(), Vista()))
        self.assertTrue(puede(self.profesor_a, 'modulo-se02', 'listar'))
        self.assertFalse(puede(self.profesor_a, 'modulo-se02', 'crear'))

    def test_rol_inactivo_no_concede_permisos(self):
        rol = self._crear_rol_collegiado('Suspendido')
        Modelo = ModeloPermitido.objects.create(nombre='modulo-se02-inactivo')
        Accion_ = Accion.objects.get_or_create(nombre='listar')[0]
        PermisoRol.objects.create(rol=rol, modelo=Modelo, accion=Accion_)
        self.profesor_a.roles_extras.add(rol)
        rol.activo = False
        rol.save(update_fields=['activo'])
        self.assertFalse(puede(self.profesor_a, 'modulo-se02-inactivo', 'listar'))
        self.assertEqual(
            [r.pk for r in roles_efectivos(self.profesor_a)],
            [self.rol_profesor.pk],
        )

    def test_permisos_efectivos_son_union_de_rol_base_y_extras(self):
        rol = self._crear_rol_collegiado('Union')
        Modelo = ModeloPermitido.objects.get_or_create(nombre='horario')[0]
        Accion_ = Accion.objects.get_or_create(nombre='listar')[0]
        PermisoRol.objects.create(rol=rol, modelo=Modelo, accion=Accion_)
        estudiante = ModeloPermitido.objects.get_or_create(nombre='estudiante')[0]
        PermisoRol.objects.get_or_create(
            rol=self.rol_profesor, modelo=estudiante, accion=Accion_,
        )
        self.profesor_a.roles_extras.add(rol)
        pares = permisos_funcionales(self.profesor_a)
        # PermisoRol base del rol Profesor (curso/estudiante listar) + horario.
        self.assertIn(('horario', 'listar'), pares)
        self.assertIn(('estudiante', 'listar'), pares)


class ComponentesInterfazTests(BaseHUSe02):
    def _url_componentes(self, rol):
        return reverse('rol-componentes', args=[rol.pk])

    def test_admin_configura_componentes_visibles_y_editables(self):
        rol = self._crear_rol_collegiado('UI')
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_componentes(rol),
            {'componentes': [
                {'componente': 'formulario:usuario.email', 'visible': True, 'editable': False},
                {'componente': 'boton:usuarios.eliminar', 'visible': False},
            ]},
            format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(respuesta.data['componentes']), 2)
        self.assertEqual(
            PermisoComponente.objects.filter(rol=rol).count(), 2,
        )

    def test_permisos_ui_efectivos_por_fusion_de_roles(self):
        ocultador = self._crear_rol_collegiado('Oculta')
        habilitador = self._crear_rol_collegiado('Habilita')
        PermisoComponente.objects.create(
            rol=ocultador, componente='boton:pagos.validar', visible=False,
        )
        PermisoComponente.objects.create(
            rol=habilitador, componente='boton:pagos.validar', visible=True, editable=True,
        )
        self.profesor_a.roles_extras.set([ocultador, habilitador])
        efectivos = {fila['componente']: fila for fila in permisos_ui(self.profesor_a)}
        self.assertFalse(efectivos['boton:pagos.validar']['visible'])
        self.assertTrue(efectivos['boton:pagos.validar']['editable'])

    def test_componente_sin_configuracion_visible_y_no_editable(self):
        self.assertTrue(puede_componente(self.profesor_a, 'menu:inicio'))
        self.assertFalse(puede_editar_componente(self.profesor_a, 'menu:inicio'))

    def test_componente_oculto_en_rol(self):
        rol = self._crear_rol_collegiado('Stealth')
        PermisoComponente.objects.create(rol=rol, componente='menu:finanzas', visible=False)
        self.profesor_a.roles_extras.add(rol)
        self.assertFalse(puede_componente(self.profesor_a, 'menu:finanzas'))
        self.assertFalse(puede_editar_componente(self.profesor_a, 'menu:finanzas'))


class AsignacionDeRolesTests(BaseHUSe02):
    def _url_asignacion(self, usuario):
        return reverse('usuario-roles', args=[usuario.pk])

    def test_director_asigna_rol_personalizado_a_usuario(self):
        rol = self._hacer_asignable(self._crear_rol_collegiado('Delegado'))
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_asignacion(self.profesor_a), {'rol_ids': [rol.pk]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual([fila['id'] for fila in respuesta.data['roles']], [rol.pk])
        self.assertIn(rol, self.profesor_a.roles_extras.all())

    def test_usuario_puede_recibir_varios_roles(self):
        primero = self._hacer_asignable(self._crear_rol_collegiado('Uno'))
        segundo = self._hacer_asignable(self._crear_rol_collegiado('Dos'))
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_asignacion(self.profesor_a), {'rol_ids': [primero.pk, segundo.pk]},
            format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(respuesta.data['roles']), 2)

    def test_no_puede_asignar_rol_de_otro_colegio(self):
        ajeno = self._crear_rol_collegiado('Ajeno', colegio=self.colegio_b)
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_asignacion(self.profesor_a), {'rol_ids': [ajeno.pk]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_puede_asignar_rol_inactivo(self):
        inactivo = self._crear_rol_collegiado('Inactivo')
        inactivo.activo = False
        inactivo.save(update_fields=['activo'])
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_asignacion(self.profesor_a), {'rol_ids': [inactivo.pk]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_puede_asignar_rol_sistema_como_adicional(self):
        rol_profesor = Rol.objects.get(nombre='Profesor')
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_asignacion(self.profesor_a), {'rol_ids': [rol_profesor.pk]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_delega_privilegios_superiores_al_asignar(self):
        peligroso = self._crear_rol_collegiado('Peligroso')
        Modelo = ModeloPermitido.objects.get_or_create(nombre='colegio')[0]
        Accion_ = Accion.objects.get_or_create(nombre='eliminar')[0]
        PermisoRol.objects.create(rol=peligroso, modelo=Modelo, accion=Accion_)
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_asignacion(self.profesor_a), {'rol_ids': [peligroso.pk]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_modifica_usuarios_de_otro_colegio(self):
        rol = self._crear_rol_collegiado('Lejos')
        profesor_b = Usuario.objects.create_user(
            ci='SE02-PRF-B', email='se02-prf-b@example.com', nombre='Prof', apellido='Beta',
            username='se02_prf_b', fecha_nacimiento='1985-01-01', password='Clave-Segura-123',
            rol=self.rol_profesor, unidad=self.unidad_b,
        )
        from aplicaciones.personal.models import Profesor
        Profesor.objects.create(usuario=profesor_b, unidad=self.unidad_b)
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.put(
            self._url_asignacion(profesor_b), {'rol_ids': [rol.pk]}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)


class AuditoriaTests(BaseHUSe02):
    def test_creacion_y_modificacion_de_rol_registradas(self):
        from .models import EventoAuditoria
        self.client.force_authenticate(self.superadmin)
        respuesta = self.client.post(self.url_roles, {'nombre': 'Auditado'}, format='json')
        rol_id = respuesta.data['id']
        ModeloPermitido.objects.get_or_create(nombre='colegio')
        self.client.put(
            reverse('rol-permisos', args=[rol_id]),
            {'permisos': [{'modelo': 'colegio', 'accion': 'listar'}]}, format='json',
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(entidad='ROL', accion='CREAR', entidad_id=str(rol_id)).exists(),
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(entidad='PERMISO_ROL', accion='ACTUALIZAR').exists(),
        )

    def test_componentes_y_asignacion_registrados(self):
        from .models import EventoAuditoria
        rol = self._hacer_asignable(self._crear_rol_collegiado('Auditado'))
        self.client.force_authenticate(self.director_a)
        self.client.put(
            reverse('rol-componentes', args=[rol.pk]),
            {'componentes': [{'componente': 'menu:x'}]}, format='json',
        )
        self.client.put(
            reverse('usuario-roles', args=[self.profesor_a.pk]),
            {'rol_ids': [rol.pk]}, format='json',
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(entidad='PERMISO_COMPONENTE').exists(),
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(entidad='ASIGNACION_ROLES').exists(),
        )

    def test_revocacion_de_permisos_registrada(self):
        from .models import EventoAuditoria
        rol = self._crear_rol_collegiado('Revocado')
        PermisoRol.objects.create(
            rol=rol,
            modelo=ModeloPermitido.objects.get_or_create(nombre='estudiante')[0],
            accion=Accion.objects.get_or_create(nombre='listar')[0],
        )
        self.client.force_authenticate(self.director_a)
        self.client.put(
            reverse('rol-permisos', args=[rol.pk]), {'permisos': []}, format='json',
        )
        self.assertFalse(PermisoRol.objects.filter(rol=rol).exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                entidad='PERMISO_ROL', entidad_id=str(rol.pk),
            ).exists(),
        )


class CatalogosTests(BaseHUSe02):
    def test_catalogo_de_acciones_incluye_las_nuevas(self):
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.get(self.url_acciones)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        nombres = {fila['nombre'] for fila in respuesta.data}
        self.assertLessEqual(
            {'listar', 'crear', 'editar', 'eliminar', 'desactivar', 'aprobar',
             'exportar', 'administrar'},
            nombres,
        )

    def test_catalogo_de_modelos(self):
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.get(self.url_modelos)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        nombres = {fila['nombre'] for fila in respuesta.data}
        self.assertIn('rol', nombres)
        self.assertIn('rol', nombres)


class Interaccion1RolesDinamicosTests(BaseHUSe02):
    """Cobertura focalizada del contrato dinámico de roles HU-SE02."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for nombre in ('SuperAdmin', 'Admin', 'Profesor', 'Tutor', 'Estudiante', 'Regente'):
            Rol.objects.get_or_create(
                nombre=nombre, colegio=None,
                defaults={'categoria': Rol.Categoria.BASE},
            )
        Rol.objects.filter(
            nombre__in=('SuperAdmin', 'Admin', 'Profesor', 'Tutor', 'Estudiante', 'Regente'),
            colegio=None,
        ).update(categoria=Rol.Categoria.BASE)

    def test_seis_roles_base_conservan_ids_y_regente_aparece(self):
        nombres = {'SuperAdmin', 'Admin', 'Profesor', 'Tutor', 'Estudiante', 'Regente'}
        roles = Rol.objects.filter(nombre__in=nombres, colegio__isnull=True)
        self.assertEqual(set(roles.values_list('nombre', flat=True)), nombres)
        self.assertTrue(all(rol.categoria == Rol.Categoria.BASE for rol in roles))
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.get(self.url_roles)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        nombres_visibles = {item['nombre'] for item in respuesta.data}
        self.assertIn('Regente', nombres_visibles)
        self.assertNotIn('SuperAdmin', nombres_visibles)

    def test_rol_funcional_no_aparece_como_base_y_superadmin_crea_sistema(self):
        self.client.force_authenticate(self.superadmin)
        respuesta = self.client.post(self.url_roles, {'nombre': 'Plantilla Regencia'}, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        rol = Rol.objects.get(pk=respuesta.data['id'])
        self.assertEqual(rol.categoria, Rol.Categoria.FUNCIONAL)
        self.assertEqual(rol.alcance, 'SISTEMA')
        base = self.client.get(self.url_roles).data
        self.assertNotIn(rol.pk, {item['id'] for item in base})

    def test_superadmin_y_director_crean_roles_de_colegio_y_unidad(self):
        self.client.force_authenticate(self.superadmin)
        colegio = self.client.post(self.url_roles, {
            'nombre': 'Coordinador Colegio', 'colegio_id': self.colegio_a.pk,
        }, format='json')
        unidad = self.client.post(self.url_roles, {
            'nombre': 'Coordinador Unidad', 'colegio_id': self.colegio_a.pk,
            'unidad_id': self.unidad_a.pk,
        }, format='json')
        self.assertEqual(colegio.status_code, status.HTTP_201_CREATED)
        self.assertEqual(unidad.status_code, status.HTTP_201_CREATED)
        self.assertEqual(unidad.data['alcance'], 'UNIDAD')
        self.client.force_authenticate(self.director_a)
        propio = self.client.post(self.url_roles, {
            'nombre': 'Rol Director Unidad', 'unidad_id': self.unidad_a.pk,
        }, format='json')
        ajeno = self.client.post(self.url_roles, {
            'nombre': 'Rol Director Ajeno', 'colegio_id': self.colegio_b.pk,
        }, format='json')
        self.assertEqual(propio.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ajeno.status_code, status.HTTP_403_FORBIDDEN)

    def test_director_no_modifica_sistema_ni_secretaria_escribe(self):
        self.client.force_authenticate(self.director_a)
        sistema = Rol.objects.get(nombre='Regente')
        self.assertEqual(
            self.client.patch(reverse('rol-detalle', args=[sistema.pk]), {'descripcion': 'x'}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )
        secretaria = Usuario.objects.create_user(
            ci='SE02-SEC', email='se02-sec@example.com', nombre='Sec', apellido='Alfa',
            username='se02_sec', fecha_nacimiento='1980-01-01', password='Clave-Segura-123',
            rol=self.rol_admin, unidad=self.unidad_a,
        )
        Puesto.objects.get_or_create(nombre='Secretaria')
        from .models import Admin
        Admin.objects.create(usuario=secretaria, puesto=Puesto.objects.get(nombre='Secretaria'), unidad=self.unidad_a, colegio=self.colegio_a)
        self.client.force_authenticate(secretaria)
        self.assertEqual(self.client.post(self.url_roles, {'nombre': 'No'}, format='json').status_code, status.HTTP_403_FORBIDDEN)

    def test_dependencia_listar_y_asignacion_sin_permisos(self):
        rol = self._crear_rol_collegiado('Dependencias')
        self.client.force_authenticate(self.superadmin)
        respuesta = self.client.put(reverse('rol-permisos', args=[rol.pk]), {
            'permisos': [{'modelo': 'curso', 'accion': 'editar'}],
        }, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(self.url_roles, {'asignables': '1'}).status_code, status.HTTP_200_OK)
        self.assertNotIn(rol.pk, {item['id'] for item in self.client.get(self.url_roles, {'asignables': '1'}).data})

    def test_get_permisos_devuelve_directos_actuales(self):
        rol = self._crear_rol_collegiado('Lectura')
        self.client.force_authenticate(self.superadmin)
        self.assertEqual(self.client.put(reverse('rol-permisos', args=[rol.pk]), {
            'permisos': [{'modelo': 'rol', 'accion': 'listar'}],
        }, format='json').status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.get(reverse('rol-permisos', args=[rol.pk]))
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data['permisos'], [{'modelo': 'rol', 'accion': 'listar'}])

    def test_roles_inactivos_sin_permisos_y_base_no_son_extras(self):
        sin_permisos = self._crear_rol_collegiado('Sin permisos')
        inactivo = self._crear_rol_collegiado('Inactivo')
        inactivo.activo = False
        inactivo.save(update_fields=['activo'])
        self.client.force_authenticate(self.director_a)
        for rol in (sin_permisos, inactivo, self.rol_profesor):
            respuesta = self.client.put(
                reverse('usuario-roles', args=[self.profesor_a.pk]),
                {'rol_ids': [rol.pk]}, format='json',
            )
            self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_unidad_ajena_no_se_puede_usar_en_rol_del_director(self):
        self.client.force_authenticate(self.director_a)
        respuesta = self.client.post(self.url_roles, {
            'nombre': 'Unidad Ajena', 'unidad_id': self.unidad_b.pk,
        }, format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

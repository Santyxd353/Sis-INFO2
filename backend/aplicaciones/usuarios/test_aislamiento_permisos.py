from rest_framework.test import APIRequestFactory, force_authenticate

from aplicaciones.suscripciones.tests_hu_se01 import BaseSuscripcionesTests
from .models import Rol
from .permissions import IsSuperAdmin
from .privilegios import roles_efectivos
from .tenancy import es_superadmin


class PrivilegiosInstitucionalesTests(BaseSuscripcionesTests):
    def test_rol_local_no_concede_superadministracion(self):
        rol = Rol.objects.create(nombre='SuperAdmin', colegio=self.colegio_a)
        usuario = self.profesor_a
        usuario.rol = rol
        usuario.save(update_fields=['rol'])
        request = APIRequestFactory().get('/')
        force_authenticate(request, user=usuario)
        request.user = usuario
        self.assertFalse(es_superadmin(usuario))
        self.assertFalse(IsSuperAdmin().has_permission(request, None))

    def test_roles_extra_de_otro_colegio_no_conceden_permisos(self):
        ajeno = Rol.objects.create(nombre='Rol ajeno', colegio=self.colegio_b)
        self.profesor_a.roles_extras.add(ajeno)
        self.assertNotIn(ajeno.pk, [rol.pk for rol in roles_efectivos(self.profesor_a)])

    def test_facturacion_solo_para_perfiles_autorizados(self):
        self.client.force_authenticate(self.profesor_a)
        self.assertEqual(self.client.get('/api/suscripciones/suscripciones/').status_code, 403)
        self.assertEqual(self.client.get('/api/suscripciones/suscripciones/mi-estado/').status_code, 403)
        self.assertEqual(self.client.get('/api/suscripciones/pagos/').status_code, 403)
        self.client.force_authenticate(self.director_a)
        self.assertEqual(self.client.get('/api/suscripciones/suscripciones/mi-estado/').status_code, 200)
        self.assertEqual(self.client.get('/api/suscripciones/pagos/').status_code, 200)

    def test_suscripcion_restringida_bloquea_infraestructura_aun_con_permiso(self):
        from .models import Accion, ModeloPermitido, PermisoPuesto
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='modulo')
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        PermisoPuesto.objects.get_or_create(puesto=self.puesto_director, modelo=modelo, accion=accion)
        self.colegio_a.requiere_suscripcion = True
        self.colegio_a.save(update_fields=['requiere_suscripcion'])
        self.client.force_authenticate(self.director_a)
        self.assertEqual(self.client.get('/api/institucion/modulos/').status_code, 403)
        self.assertEqual(self.client.get('/api/suscripciones/suscripciones/mi-estado/').status_code, 200)

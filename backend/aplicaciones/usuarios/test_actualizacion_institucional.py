from .test_tenancy_scope import AlcanceInstitucionalTests
from .models import Accion, ModeloPermitido, PermisoPuesto
from .tenancy import ErrorAlcanceInstitucional, resolver_alcance


class ActualizacionInstitucionalTests(AlcanceInstitucionalTests):
    def setUp(self):
        self.client.force_authenticate(self.superusuario)
        self.url = f'/api/usuarios/usuarios/{self.secretaria.pk}/'

    def estado(self):
        self.secretaria.refresh_from_db()
        admin = self.secretaria.admin
        admin.refresh_from_db()
        return self.secretaria.unidad_id, admin.unidad_id, admin.colegio_id, admin.puesto_id

    def test_patch_null_con_otra_unidad_no_modifica_nada(self):
        antes = self.estado()
        response = self.client.patch(self.url, {'puesto_id': None, 'unidad_id': self.b1.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.estado(), antes)

    def test_patch_omitido_valida_y_conserva_puesto(self):
        antes = self.estado()
        self.assertEqual(self.client.patch(self.url, {'unidad_id': self.b1.pk}, format='json').status_code, 400)
        self.assertEqual(self.estado(), antes)
        self.assertEqual(self.client.patch(self.url, {'unidad_id': self.a2.pk}, format='json').status_code, 200)
        self.assertEqual(self.estado(), (self.a2.pk, self.a2.pk, self.colegio_a.pk, antes[3]))

    def test_director_sin_unidad_y_unidad_ajena(self):
        url = f'/api/usuarios/usuarios/{self.director.pk}/'
        self.assertEqual(self.client.patch(url, {'unidad_id': None}, format='json').status_code, 200)
        self.assertEqual(resolver_alcance(self.director)['tipo'], 'COLEGIO')
        self.assertEqual(self.client.patch(url, {'unidad_id': self.b1.pk}, format='json').status_code, 400)

    def test_divergencia_preexistente_no_genera_alcance_global(self):
        self.secretaria.admin.colegio = self.colegio_b
        self.secretaria.admin.save(update_fields=['colegio'])
        with self.assertRaises(ErrorAlcanceInstitucional):
            resolver_alcance(self.secretaria)
        self.assertEqual(self.client.patch(self.url, {'nombre': 'Prueba'}, format='json').status_code, 400)

    def test_divergencia_de_unidades_preexistente_se_rechaza(self):
        self.secretaria.admin.unidad = self.a2
        self.secretaria.admin.save(update_fields=['unidad'])
        with self.assertRaises(ErrorAlcanceInstitucional):
            resolver_alcance(self.secretaria)
        self.assertEqual(self.client.patch(self.url, {'nombre': 'Prueba'}, format='json').status_code, 400)

    def test_put_rechaza_puesto_nulo_y_no_modifica(self):
        antes = self.estado()
        datos = {'ci': self.secretaria.ci, 'username': self.secretaria.username,
                 'email': self.secretaria.email, 'nombre': self.secretaria.nombre,
                 'apellido': self.secretaria.apellido, 'rol_id': self.rol_admin.pk,
                 'puesto_id': None, 'unidad_id': self.b1.pk}
        self.assertEqual(self.client.put(self.url, datos, format='json').status_code, 400)
        self.assertEqual(self.estado(), antes)

    def test_director_no_asigna_unidad_ajena(self):
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='usuario')
        accion, _ = Accion.objects.get_or_create(nombre='editar')
        PermisoPuesto.objects.get_or_create(puesto=self.puesto_director, modelo=modelo, accion=accion)
        self.client.force_authenticate(self.director)
        antes = self.estado()
        self.assertIn(self.client.patch(self.url, {'unidad_id': self.b1.pk}, format='json').status_code, (400, 403))
        self.assertEqual(self.estado(), antes)

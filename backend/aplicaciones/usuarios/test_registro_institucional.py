from datetime import date
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from aplicaciones.suscripciones.models import MetodoPago, Plan, Suscripcion
from aplicaciones.suscripciones.servicios import calcular_vencimiento, restriccion_activa
from .models import Puesto, RegistroInstitucional, Rol, Usuario
from .tenancy import resolver_alcance


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', FRONTEND_PUBLIC_URL='http://example.test')
class RegistroInstitucionalTests(APITestCase):
    def setUp(self):
        Rol.objects.get_or_create(nombre='Admin', colegio=None)
        Puesto.objects.get_or_create(nombre='Director')
        MetodoPago.objects.get_or_create(codigo='TARJETA', defaults={'nombre': 'Tarjeta'})

    def test_registro_verificacion_y_aislamiento(self):
        plan = Plan.objects.create(nombre='Plan USD', precio='20.00', moneda='USD', periodicidad='MENSUAL')
        payload = {'nombre': 'Ana', 'apellido': 'Prueba', 'username': 'ana.prueba', 'email': 'ana@example.test',
                   'password': 'S3guro!ejemplo2026', 'colegio': 'Colegio prueba', 'pais': 'US',
                   'region': 'Florida', 'ciudad': 'Miami', 'direccion': 'Calle 1', 'telefono': '+13055550123',
                   'telefono_responsable': '+13055550124',
                   'zona_horaria': 'America/New_York', 'idioma': 'en', 'razon_facturacion': 'Colegio prueba',
                   'email_facturacion': 'facturas@example.test', 'acepta_condiciones': True, 'plan': plan.pk,
                   'metodo_pago': 'TARJETA', 'pago_referencia': 'SIM-TARJETA-4242'}
        result = self.client.post('/api/usuarios/registro-institucional/', payload, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        user = Usuario.objects.get(email='ana@example.test')
        self.assertTrue(user.is_active)
        registro = RegistroInstitucional.objects.get(usuario=user)
        self.assertEqual(registro.plan_seleccionado_id, plan.pk)
        self.assertEqual(user.username, 'ana.prueba')
        self.assertEqual(user.telefono, '+13055550124')
        self.assertEqual(Suscripcion.objects.get(colegio=registro.colegio).estado, Suscripcion.Estado.PENDIENTE)
        self.assertTrue(registro.colegio.requiere_suscripcion)
        self.assertIsNotNone(restriccion_activa(registro.colegio))
        self.assertEqual(resolver_alcance(user)['colegio_id'], registro.colegio_id)
        # Compatibilidad para registros creados antes de habilitar el acceso
        # inmediato: las credenciales correctas recuperan su cuenta.
        user.is_active = False
        user.save(update_fields=['is_active'])
        login = self.client.post(
            '/api/usuarios/login/',
            {'email': payload['email'], 'password': payload['password']},
            format='json',
        )
        self.assertEqual(login.status_code, 200, login.data)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        link = next(word for word in mail.outbox[0].body.split() if word.startswith('http'))
        token = parse_qs(urlparse(link).query)['token'][0]
        verificacion = self.client.post('/api/usuarios/verificar-correo/', {'token': token}, format='json')
        self.assertEqual(verificacion.status_code, 200)
        self.assertEqual(verificacion.data['plan'], plan.pk)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(self.client.post('/api/usuarios/verificar-correo/', {'token': token}, format='json').status_code, 400)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + login.data['access'])

    def test_registro_rechaza_datos_invalidos(self):
        response = self.client.post('/api/usuarios/registro-institucional/', {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(RegistroInstitucional.objects.exists())

    @override_settings(ENVIRONMENT='production', EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_registro_sin_correo_crea_la_cuenta(self):
        payload = {
            'nombre': 'Ana', 'apellido': 'Prueba', 'username': 'ana.sin.correo', 'email': 'sin-correo@example.test',
            'password': 'S3guro!ejemplo2026', 'colegio': 'Colegio sin correo', 'pais': 'BO',
            'region': 'Santa Cruz', 'ciudad': 'Santa Cruz', 'direccion': 'Calle 1', 'telefono': '+59170000001',
            'telefono_responsable': '+59170000002', 'zona_horaria': 'America/La_Paz', 'idioma': 'es',
            'razon_facturacion': 'Colegio sin correo', 'email_facturacion': 'facturas@example.test',
            'acepta_condiciones': True,
        }
        with patch('aplicaciones.usuarios.registro_api.send_mail') as envio:
            resultado = self.client.post('/api/usuarios/registro-institucional/', payload, format='json')
        self.assertEqual(resultado.status_code, 201, resultado.data)
        self.assertEqual(resultado.data['modo_correo'], 'no_disponible')
        envio.assert_not_called()
        registro = RegistroInstitucional.objects.get(usuario__email=payload['email'])
        self.assertTrue(registro.usuario.is_active)
        self.assertIsNone(registro.verificado_at)
        self.assertEqual(self.client.post('/api/usuarios/login/', {
            'email': payload['email'], 'password': payload['password'],
        }, format='json').status_code, 200)

    def test_periodos_usan_calendario(self):
        self.assertEqual(calcular_vencimiento(date(2028, 1, 31), 'MENSUAL'), date(2028, 2, 29))
        self.assertEqual(calcular_vencimiento(date(2028, 2, 29), 'ANUAL'), date(2029, 2, 28))

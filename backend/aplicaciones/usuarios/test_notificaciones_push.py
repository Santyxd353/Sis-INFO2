from unittest.mock import patch

from rest_framework.test import APITestCase

from .models import DispositivoNotificacion, Rol, Usuario
from .notificaciones import enviar_notificacion


class RegistroDispositivoTests(APITestCase):
    url_registrar = '/api/usuarios/dispositivos/registrar/'
    url_desregistrar = '/api/usuarios/dispositivos/desregistrar/'
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        rol_estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante')
        cls.usuario = Usuario.objects.create_user(
            ci='PUSH-EST', email='push-est@example.com', nombre='Push', apellido='Est',
            username='push_est', fecha_nacimiento='2014-01-01', password=cls.password,
            rol=rol_estudiante,
        )
        otro_usuario = Usuario.objects.create_user(
            ci='PUSH-EST2', email='push-est2@example.com', nombre='Push2', apellido='Est2',
            username='push_est2', fecha_nacimiento='2014-01-01', password=cls.password,
            rol=rol_estudiante,
        )
        cls.otro_usuario = otro_usuario

    def autenticar(self, usuario=None):
        self.client.force_authenticate(usuario or self.usuario)

    def test_anonimo_no_puede_registrar(self):
        response = self.client.post(self.url_registrar, {'token': 'x', 'plataforma': 'ANDROID'}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_registrar_crea_el_dispositivo(self):
        self.autenticar()
        response = self.client.post(
            self.url_registrar, {'token': 'ExponentPushToken[abc123]', 'plataforma': 'android'}, format='json',
        )
        self.assertEqual(response.status_code, 204)
        dispositivo = DispositivoNotificacion.objects.get(token='ExponentPushToken[abc123]')
        self.assertEqual(dispositivo.usuario, self.usuario)
        self.assertEqual(dispositivo.plataforma, 'ANDROID')
        self.assertTrue(dispositivo.activo)

    def test_registrar_dos_veces_no_duplica(self):
        self.autenticar()
        payload = {'token': 'ExponentPushToken[dup]', 'plataforma': 'ANDROID'}
        self.client.post(self.url_registrar, payload, format='json')
        self.client.post(self.url_registrar, payload, format='json')
        self.assertEqual(DispositivoNotificacion.objects.filter(token='ExponentPushToken[dup]').count(), 1)

    def test_registrar_reasigna_el_token_a_quien_inicio_sesion_ahora(self):
        """Mismo dispositivo, usuario distinto (p.ej. otro hijo con la misma
        tablet): el token se reasigna, no se crea un duplicado rechazado."""
        DispositivoNotificacion.objects.create(
            usuario=self.otro_usuario, token='ExponentPushToken[compartido]', plataforma='ANDROID',
        )
        self.autenticar(self.usuario)
        response = self.client.post(
            self.url_registrar, {'token': 'ExponentPushToken[compartido]', 'plataforma': 'ANDROID'}, format='json',
        )
        self.assertEqual(response.status_code, 204)
        dispositivo = DispositivoNotificacion.objects.get(token='ExponentPushToken[compartido]')
        self.assertEqual(dispositivo.usuario, self.usuario)

    def test_rechaza_plataforma_invalida(self):
        self.autenticar()
        response = self.client.post(
            self.url_registrar, {'token': 'x', 'plataforma': 'WINDOWS_PHONE'}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_desregistrar_desactiva_sin_borrar(self):
        self.autenticar()
        self.client.post(self.url_registrar, {'token': 'ExponentPushToken[baja]', 'plataforma': 'IOS'}, format='json')
        response = self.client.post(self.url_desregistrar, {'token': 'ExponentPushToken[baja]'}, format='json')
        self.assertEqual(response.status_code, 204)
        dispositivo = DispositivoNotificacion.objects.get(token='ExponentPushToken[baja]')
        self.assertFalse(dispositivo.activo)

    def test_no_puede_desregistrar_el_token_de_otro_usuario(self):
        DispositivoNotificacion.objects.create(
            usuario=self.otro_usuario, token='ExponentPushToken[ajeno]', plataforma='IOS',
        )
        self.autenticar(self.usuario)
        self.client.post(self.url_desregistrar, {'token': 'ExponentPushToken[ajeno]'}, format='json')
        dispositivo = DispositivoNotificacion.objects.get(token='ExponentPushToken[ajeno]')
        self.assertTrue(dispositivo.activo)


class EnviarNotificacionTests(APITestCase):
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        rol_estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante')
        cls.usuario = Usuario.objects.create_user(
            ci='PUSH-ENV', email='push-env@example.com', nombre='Env', apellido='Push',
            username='push_env', fecha_nacimiento='2014-01-01', password=cls.password,
            rol=rol_estudiante,
        )

    def test_sin_dispositivos_no_llama_a_expo(self):
        with patch('aplicaciones.usuarios.notificaciones.requests.post') as post:
            enviar_notificacion([self.usuario.pk], 'Título', 'Cuerpo')
        post.assert_not_called()

    def test_con_dispositivo_activo_llama_a_expo_con_el_token(self):
        DispositivoNotificacion.objects.create(usuario=self.usuario, token='ExponentPushToken[ok]', plataforma='ANDROID')
        with patch('aplicaciones.usuarios.notificaciones.requests.post') as post:
            post.return_value.raise_for_status.return_value = None
            enviar_notificacion([self.usuario.pk], 'Título', 'Cuerpo', datos={'x': 1})
        post.assert_called_once()
        mensajes_enviados = post.call_args.kwargs['json']
        self.assertEqual(mensajes_enviados, [{'to': 'ExponentPushToken[ok]', 'title': 'Título',
            'body': 'Cuerpo', 'data': {'x': 1}, 'channelId': 'default-v2'}])

    def test_dispositivo_inactivo_no_recibe_notificacion(self):
        DispositivoNotificacion.objects.create(
            usuario=self.usuario, token='ExponentPushToken[inactivo]', plataforma='ANDROID', activo=False,
        )
        with patch('aplicaciones.usuarios.notificaciones.requests.post') as post:
            enviar_notificacion([self.usuario.pk], 'Título', 'Cuerpo')
        post.assert_not_called()

    def test_lotes_expo_no_superan_cien_dispositivos(self):
        DispositivoNotificacion.objects.bulk_create([
            DispositivoNotificacion(usuario=self.usuario, token=f'ExponentPushToken[batch-{i}]', plataforma='ANDROID')
            for i in range(205)
        ])
        with patch('aplicaciones.usuarios.notificaciones.requests.post') as post:
            enviar_notificacion([self.usuario.pk], 'Título', 'Cuerpo')
        self.assertEqual([len(call.kwargs['json']) for call in post.call_args_list], [100, 100, 5])

    def test_error_de_red_no_lanza_excepcion(self):
        import requests
        DispositivoNotificacion.objects.create(usuario=self.usuario, token='ExponentPushToken[falla]', plataforma='ANDROID')
        with patch('aplicaciones.usuarios.notificaciones.requests.post', side_effect=requests.RequestException('caído')):
            enviar_notificacion([self.usuario.pk], 'Título', 'Cuerpo')  # no debe lanzar

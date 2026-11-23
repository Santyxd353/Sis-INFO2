from datetime import timedelta

from django.db import DatabaseError, transaction
from rest_framework import status
from rest_framework.test import APITestCase, APIRequestFactory

from aplicaciones.institucion.models import Colegio, UnidadEducativa

from .auditoria import registrar_evento, sanitizar_cambios
from .utils import get_client_ip, registrar_bitacora
from .models import (
    Accion, Admin, Bitacora, EventoAuditoria, ModeloPermitido, PermisoPuesto, Puesto, Rol,
    Usuario,
)


class AuditoriaHU05Tests(APITestCase):
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio_a = Colegio.objects.create(
            nombre='Colegio A', direccion='Local A', telefono='70000001',
        )
        cls.colegio_b = Colegio.objects.create(
            nombre='Colegio B', direccion='Local B', telefono='70000002',
        )
        cls.unidad_a1 = UnidadEducativa.objects.create(
            colegio=cls.colegio_a, codigo_sie='AUD-A1', turno='TARDE', nombre='A1',
        )
        cls.unidad_a2 = UnidadEducativa.objects.create(
            colegio=cls.colegio_a, codigo_sie='AUD-A2', turno='MAÑANA', nombre='A2',
        )
        cls.unidad_b1 = UnidadEducativa.objects.create(
            colegio=cls.colegio_b, codigo_sie='AUD-B1', turno='NOCHE', nombre='B1',
        )
        cls.superusuario = Usuario.objects.create_superuser(
            ci='AUD-SUPER', email='aud-super@example.com', nombre='Super', apellido='Auditor',
            username='aud_super', fecha_nacimiento='1990-01-01', password=cls.password,
        )
        rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        rol_tutor, _ = Rol.objects.get_or_create(nombre='Tutor')
        puesto_director, _ = Puesto.objects.get_or_create(nombre='Director')
        puesto_secretaria = Puesto.objects.create(nombre='Secretaría')
        modelo_auditoria, _ = ModeloPermitido.objects.get_or_create(nombre='auditoria')
        listar, _ = Accion.objects.get_or_create(nombre='listar')
        PermisoPuesto.objects.get_or_create(
            puesto=puesto_director, modelo=modelo_auditoria, accion=listar,
        )
        cls.director = Usuario.objects.create_user(
            ci='AUD-DIR', email='aud-dir@example.com', nombre='Director', apellido='A',
            username='aud_dir', fecha_nacimiento='1980-01-01', password=cls.password,
            rol=rol_admin, unidad=cls.unidad_a1,
        )
        Admin.objects.create(usuario=cls.director, puesto=puesto_director, unidad=cls.unidad_a1, colegio=cls.colegio_a)
        cls.admin = Usuario.objects.create_user(
            ci='AUD-ADM', email='aud-admin@example.com', nombre='Admin', apellido='A',
            username='aud_admin', fecha_nacimiento='1981-01-01', password=cls.password,
            rol=rol_admin, unidad=cls.unidad_a1,
        )
        Admin.objects.create(usuario=cls.admin, puesto=puesto_secretaria, unidad=cls.unidad_a1, colegio=cls.colegio_a)
        cls.sin_permiso = Usuario.objects.create_user(
            ci='AUD-TUT', email='aud-tutor@example.com', nombre='Tutor', apellido='A',
            username='aud_tutor', fecha_nacimiento='1982-01-01', password=cls.password,
            rol=rol_tutor, unidad=cls.unidad_a1,
        )

    def request_auditable(self, usuario=None, ip='192.0.2.10'):
        request = APIRequestFactory().get('/prueba', REMOTE_ADDR=ip)
        request.user = usuario or self.superusuario
        return request

    def crear_evento(self, unidad=None, accion='CREAR', entidad='USUARIO', usuario=None):
        return registrar_evento(
            accion=accion, entidad=entidad,
            request=self.request_auditable(usuario), usuario=usuario or self.superusuario,
            unidad=unidad, entidad_id='10', cambios={'campos': ['estado']},
        )

    def test_login_exitoso_genera_evento(self):
        response = self.client.post('/api/usuarios/login/', {
            'email': self.superusuario.email, 'password': self.password,
        }, format='json', REMOTE_ADDR='192.0.2.20')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        evento = EventoAuditoria.objects.get(accion='LOGIN_EXITOSO')
        self.assertEqual(evento.usuario, self.superusuario.pk)
        self.assertNotEqual(evento.ip_hash, '192.0.2.20')

    def test_login_fallido_no_guarda_credenciales(self):
        response = self.client.post('/api/usuarios/login/', {
            'email': 'persona@example.com', 'password': 'secreto-visible',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        evento = EventoAuditoria.objects.get(accion='LOGIN_FALLIDO')
        representacion = str(evento.__dict__)
        self.assertNotIn('secreto-visible', representacion)
        self.assertNotIn('persona@example.com', representacion)

    def test_logout_exitoso_genera_evento(self):
        login = self.client.post('/api/usuarios/login/', {
            'email': self.superusuario.email, 'password': self.password,
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        response = self.client.post('/api/usuarios/logout/', {
            'refresh': login.data['refresh'],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(EventoAuditoria.objects.filter(
            accion='LOGOUT', cambios_sanitizados__resultado='EXITOSO',
        ).exists())

    def test_ip_se_pseudonimiza_con_hmac_estable(self):
        primero = self.crear_evento()
        segundo = self.crear_evento(accion='ACTUALIZAR')
        self.assertEqual(primero.ip_hash, segundo.ip_hash)
        self.assertEqual(len(primero.ip_hash), 64)

    def test_bitacora_heredada_no_guarda_ip_ni_detalle_personal(self):
        bitacora = registrar_bitacora(
            self.superusuario, '192.0.2.10', 'estudiante', 'crear', 'Crear estudiante Ana Pérez',
        )
        self.assertIsInstance(bitacora, Bitacora)
        self.assertNotEqual(bitacora.ip, '192.0.2.10')
        self.assertNotIn('Ana Pérez', bitacora.descripcion)

    def test_x_forwarded_for_requiere_proxy_confiable(self):
        request = APIRequestFactory().get(
            '/prueba', REMOTE_ADDR='198.51.100.3', HTTP_X_FORWARDED_FOR='192.0.2.8',
        )
        self.assertEqual(get_client_ip(request), '198.51.100.3')

    def test_correlacion_por_solicitud_y_metadata_del_cliente(self):
        response = self.client.post(
            '/api/usuarios/login/',
            {'email': self.superusuario.email, 'password': self.password},
            format='json',
            HTTP_X_CLIENT_TIME='2032-05-06T07:08:09+00:00',
            HTTP_X_CLIENT_TIMEZONE='America/La_Paz',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        evento = EventoAuditoria.objects.get(accion='LOGIN_EXITOSO')
        self.assertEqual(str(evento.correlacion), response['X-Correlation-ID'])
        self.assertEqual(evento.zona_cliente, 'America/La_Paz')
        self.assertEqual(evento.fecha_cliente.isoformat(), '2032-05-06T07:08:09+00:00')

    def test_eventos_de_la_misma_solicitud_comparten_correlacion(self):
        request = self.request_auditable()
        request.audit_correlation_id = '5e198f2d-257d-494a-b1b8-e12709a6451e'
        primero = registrar_evento(
            accion='CREAR', entidad='USUARIO', request=request, usuario=self.superusuario,
        )
        segundo = registrar_evento(
            accion='ACTUALIZAR', entidad='USUARIO', request=request, usuario=self.superusuario,
        )
        self.assertEqual(primero.correlacion, segundo.correlacion)

    def test_sanitizacion_descarta_secretos_y_datos_personales(self):
        cambios = sanitizar_cambios({
            'campos': ['nombre', 'password', 'email', 'estado'],
            'token': 'prohibido', 'resultado': 'OK', 'objeto': {'ci': '123'},
        })
        self.assertEqual(
            cambios, {'campos': ['email', 'estado', 'nombre'], 'resultado': 'OK'},
        )

    def test_servicio_resuelve_ambito_unidad_y_colegio(self):
        evento = self.crear_evento(unidad=self.unidad_a1)
        self.assertEqual(evento.ambito, 'UNIDAD')
        self.assertEqual(evento.colegio, self.colegio_a)

    def test_superadmin_lista_paginada_y_ordenada(self):
        antiguo = self.crear_evento(unidad=self.unidad_a1)
        nuevo = self.crear_evento(unidad=self.unidad_b1, accion='ACTUALIZAR')
        self.client.force_authenticate(self.superusuario)
        response = self.client.get('/api/usuarios/auditoria/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['results'][0]['id'], nuevo.pk)

    def test_filtros_accion_entidad_usuario_y_fechas(self):
        evento = self.crear_evento(unidad=self.unidad_a1, accion='ACTUALIZAR')
        self.crear_evento(unidad=self.unidad_a1, accion='CREAR', entidad='INSCRIPCION')
        self.client.force_authenticate(self.superusuario)
        hoy = evento.created_at.date().isoformat()
        response = self.client.get('/api/usuarios/auditoria/', {
            'accion': 'ACTUALIZAR', 'entidad': 'USUARIO',
            'usuario': self.superusuario.pk, 'desde': hoy, 'hasta': hoy,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in response.data['results']], [evento.pk])

    def test_filtro_fecha_invalida_devuelve_400(self):
        self.client.force_authenticate(self.superusuario)
        response = self.client.get('/api/usuarios/auditoria/', {'desde': 'fecha-invalida'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_es_solo_lectura(self):
        self.client.force_authenticate(self.superusuario)
        response = self.client.post('/api/usuarios/auditoria/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_api_exige_autenticacion(self):
        response = self.client.get('/api/usuarios/auditoria/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_usuario_no_autorizado_recibe_403(self):
        self.client.force_authenticate(self.sin_permiso)
        response = self.client.get('/api/usuarios/auditoria/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_director_consulta_todo_su_colegio(self):
        propio = self.crear_evento(unidad=self.unidad_a1)
        hermano = self.crear_evento(unidad=self.unidad_a2)
        self.client.force_authenticate(self.director)
        response = self.client.get('/api/usuarios/auditoria/')
        self.assertEqual(
            {item['id'] for item in response.data['results']}, {propio.pk, hermano.pk},
        )

    def test_secretaria_sin_permiso_recibe_403(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/usuarios/auditoria/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_secretaria_sin_permiso_no_recibe_eventos_y_conserva_sesion(self):
        self.crear_evento(unidad=self.unidad_a1)
        self.client.force_authenticate(self.admin)

        respuesta_auditoria = self.client.get('/api/usuarios/auditoria/')

        self.assertEqual(respuesta_auditoria.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('results', respuesta_auditoria.data)
        self.assertEqual(EventoAuditoria.objects.count(), 1)

        respuesta_perfil = self.client.get('/api/usuarios/perfil/')
        self.assertEqual(respuesta_perfil.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta_perfil.data['id'], self.admin.pk)

    def test_filtro_de_otro_colegio_es_rechazado(self):
        self.client.force_authenticate(self.director)
        response = self.client.get('/api/usuarios/auditoria/', {'colegio': self.colegio_b.pk})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_director_puede_ver_detalle_de_unidad_hermana(self):
        ajeno = self.crear_evento(unidad=self.unidad_a2)
        self.client.force_authenticate(self.director)
        response = self.client.get(f'/api/usuarios/auditoria/{ajeno.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_actualizacion_de_usuario_genera_evento_sanitizado(self):
        self.client.force_authenticate(self.superusuario)
        response = self.client.patch(
            f'/api/usuarios/usuarios/{self.sin_permiso.pk}/',
            {'telefono': '70001111'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        evento = EventoAuditoria.objects.get(accion='ACTUALIZAR', entidad='USUARIO')
        self.assertEqual(evento.entidad_id, str(self.sin_permiso.pk))
        self.assertEqual(evento.cambios_sanitizados, {'campos': ['telefono']})

    def test_eliminacion_de_usuario_genera_evento(self):
        rol_tutor = Rol.objects.get(nombre='Tutor')
        objetivo = Usuario.objects.create_user(
            ci='AUD-DEL', email='aud-del@example.com', nombre='Eliminar', apellido='Prueba',
            username='aud_del', fecha_nacimiento='1985-01-01', password=self.password,
            rol=rol_tutor, unidad=self.unidad_a1,
        )
        objetivo_id = objetivo.pk
        self.client.force_authenticate(self.superusuario)
        response = self.client.delete(f'/api/usuarios/usuarios/{objetivo_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(EventoAuditoria.objects.filter(
            accion='ELIMINAR', entidad='USUARIO', entidad_id=str(objetivo_id),
        ).exists())

    def test_evento_es_inmutable_en_orm_y_base_de_datos(self):
        evento = self.crear_evento(unidad=self.unidad_a1)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EventoAuditoria.objects.filter(pk=evento.pk).update(accion='ELIMINAR')
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                EventoAuditoria.objects.filter(pk=evento.pk).delete()

    def test_eliminar_usuario_conserva_actor_historico(self):
        objetivo = Usuario.objects.create_user(
            ci='AUD-HIST', email='aud-hist@example.com', nombre='Histórico', apellido='Prueba',
            username='aud_hist', fecha_nacimiento='1985-01-01', password=self.password,
            rol=Rol.objects.get(nombre='Tutor'), unidad=self.unidad_a1,
        )
        evento = registrar_evento(
            accion='ACTUALIZAR', entidad='USUARIO', request=self.request_auditable(objetivo),
            usuario=objetivo, entidad_id=objetivo.pk, cambios={'campos': ['estado']},
        )
        objetivo_id = objetivo.pk
        objetivo.delete()
        evento.refresh_from_db()
        self.assertEqual(evento.usuario, objetivo_id)

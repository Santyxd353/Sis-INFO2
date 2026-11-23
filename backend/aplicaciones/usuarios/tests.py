from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from django.db import IntegrityError, transaction
from django.test import TestCase

from aplicaciones.institucion.models import Colegio, UnidadEducativa

from .models import Accion, EventoAuditoria, ModeloPermitido, PermisoPuesto, Puesto, Rol, Usuario


class EventoAuditoriaTests(TestCase):
    def setUp(self):
        self.colegio = Colegio.objects.create(
            nombre='Colegio auditoría', direccion='Local', telefono='70000000',
        )
        self.unidad = UnidadEducativa.objects.create(
            colegio=self.colegio, codigo_sie='SIE-AUDITORIA', turno='TARDE',
            nombre='Unidad auditoría',
        )

    def test_evento_auditoria_acepta_ambitos_validos(self):
        global_evento = EventoAuditoria.objects.create(
            ambito='GLOBAL', accion='CONSULTAR', entidad='Prueba',
        )
        colegio_evento = EventoAuditoria.objects.create(
            ambito='COLEGIO', colegio=self.colegio, accion='CREAR', entidad='Prueba',
        )
        unidad_evento = EventoAuditoria.objects.create(
            ambito='UNIDAD', colegio=self.colegio, unidad_educativa=self.unidad,
            accion='EDITAR', entidad='Prueba', cambios_sanitizados={'campo': 'estado'},
        )

        self.assertIsNotNone(global_evento.correlacion)
        self.assertEqual(colegio_evento.colegio, self.colegio)
        self.assertEqual(unidad_evento.unidad_educativa, self.unidad)

    def test_evento_auditoria_rechaza_ambito_inconsistente(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventoAuditoria.objects.create(
                ambito='GLOBAL', colegio=self.colegio,
                accion='CREAR', entidad='Prueba',
            )


class AutenticacionApiTests(APITestCase):
    def setUp(self):
        self.password = 'Clave-Segura-123'
        self.usuario = Usuario.objects.create_superuser(
            ci='TEST-CI-001',
            email='superadmin-test@example.com',
            nombre='Super',
            apellido='Admin',
            username='superadmin_test',
            fecha_nacimiento='1990-01-01',
            password=self.password,
        )

    def login(self, password=None):
        return self.client.post(
            '/api/usuarios/login/',
            {'email': self.usuario.email, 'password': password or self.password},
            format='json',
        )

    def test_login_perfil_y_logout(self):
        login = self.login()
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn('access', login.data)
        self.assertIn('refresh', login.data)
        self.assertIn('token', login.data)
        self.assertEqual(login.data['token'], login.data['access'])
        self.assertEqual(login.data['user']['username'], self.usuario.username)
        self.assertEqual(login.data['user']['rol']['nombre'], 'SuperAdmin')

        authorization = f"Bearer {login.data['access']}"
        perfil = self.client.get(
            '/api/usuarios/perfil/',
            HTTP_AUTHORIZATION=authorization,
        )
        self.assertEqual(perfil.status_code, status.HTTP_200_OK)
        self.assertEqual(perfil.data['id'], self.usuario.id)

        for url in [
            '/api/usuarios/usuarios/',
            '/api/usuarios/roles/',
            '/api/institucion/unidades-educativas/',
            '/api/academico/grados/',
            '/api/academico/paralelos/',
            '/api/academico/cursos/',
            '/api/personal/profesores/',
            '/api/calendario/calendarios/',
            '/api/calendario/periodos/',
            '/api/calendario/feriados/',
            '/api/estudiantes/estudiantes/listar/',
            '/api/estudiantes/tutores/',
        ]:
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_AUTHORIZATION=authorization)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

        refresh_jti = RefreshToken(login.data['refresh'])['jti']
        logout = self.client.post(
            '/api/usuarios/logout/',
            {'refresh': login.data['refresh']},
            format='json',
            HTTP_AUTHORIZATION=authorization,
        )
        self.assertEqual(logout.status_code, status.HTTP_200_OK)
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=refresh_jti).exists()
        )

        refresh_reutilizado = self.client.post(
            '/api/usuarios/refresh/',
            {'refresh': login.data['refresh']},
            format='json',
        )
        self.assertEqual(refresh_reutilizado.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_invalido_no_es_404(self):
        response = self.login(password='incorrecta')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tokens_contienen_expiracion(self):
        login = self.login()
        access = AccessToken(login.data['access'])
        refresh = RefreshToken(login.data['refresh'])

        self.assertGreater(access['exp'], access['iat'])
        self.assertGreater(refresh['exp'], refresh['iat'])
        self.assertEqual(login.data['expires_in'], 15 * 60)
        self.assertEqual(login.data['access_expires_at'], access['exp'])
        self.assertEqual(login.data['refresh_expires_at'], refresh['exp'])

    def test_usuario_inactivo_no_puede_iniciar_sesion(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=['is_active'])

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_perfil_requiere_access_token_valido(self):
        sin_token = self.client.get('/api/usuarios/perfil/')
        self.assertEqual(sin_token.status_code, status.HTTP_401_UNAUTHORIZED)

        login = self.login()
        con_token = self.client.get(
            '/api/usuarios/perfil/',
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
        )
        self.assertEqual(con_token.status_code, status.HTTP_200_OK)
        self.assertEqual(con_token.data['id'], self.usuario.pk)

    def test_refresh_rota_tokens_e_invalida_el_anterior(self):
        login = self.login()
        anterior = login.data['refresh']

        renovado = self.client.post(
            '/api/usuarios/refresh/', {'refresh': anterior}, format='json',
        )
        self.assertEqual(renovado.status_code, status.HTTP_200_OK, renovado.data)
        self.assertIn('access', renovado.data)
        self.assertIn('refresh', renovado.data)
        self.assertNotEqual(renovado.data['access'], login.data['access'])
        self.assertNotEqual(renovado.data['refresh'], anterior)
        self.assertTrue(EventoAuditoria.objects.filter(
            accion='TOKEN_RENOVADO', usuario=self.usuario.pk,
        ).exists())

        reutilizado = self.client.post(
            '/api/usuarios/refresh/', {'refresh': anterior}, format='json',
        )
        self.assertEqual(reutilizado.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_revocado_no_se_reutiliza_despues_de_logout(self):
        login = self.login()
        refresh = login.data['refresh']
        authorization = f"Bearer {login.data['access']}"

        logout = self.client.post(
            '/api/usuarios/logout/', {'refresh': refresh}, format='json',
            HTTP_AUTHORIZATION=authorization,
        )

        self.assertEqual(logout.status_code, status.HTTP_200_OK, logout.data)
        reutilizado = self.client.post(
            '/api/usuarios/refresh/', {'refresh': refresh}, format='json',
        )
        self.assertEqual(reutilizado.status_code, status.HTTP_401_UNAUTHORIZED)
        evento = EventoAuditoria.objects.get(
            accion='LOGOUT', usuario=self.usuario.pk,
        )
        self.assertNotIn(refresh, str(evento.cambios_sanitizados))
        self.assertTrue(EventoAuditoria.objects.filter(
            accion='TOKEN_RECHAZADO', usuario=self.usuario.pk,
        ).exists())

    def test_access_token_alterado_es_rechazado(self):
        login = self.login()
        partes = login.data['access'].split('.')
        firma = partes[2]
        partes[2] = ('A' if firma[0] != 'A' else 'B') + firma[1:]
        alterado = '.'.join(partes)

        response = self.client.get(
            '/api/usuarios/perfil/', HTTP_AUTHORIZATION=f'Bearer {alterado}',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_usuario_sin_permiso_recibe_403(self):
        colegio = Colegio.objects.create(nombre='Colegio JWT Permiso')
        unidad = UnidadEducativa.objects.create(
            codigo_sie='JWT-PERMISO', turno='TARDE', nombre='Unidad JWT', colegio=colegio,
        )
        rol, _ = Rol.objects.get_or_create(nombre='Tutor')
        usuario = Usuario.objects.create_user(
            ci='JWT-SIN-PERMISO', email='sin-permiso@example.com', nombre='Sin',
            apellido='Permiso', username='sin_permiso', password=self.password,
            rol=rol, unidad=unidad,
        )
        login = self.client.post(
            '/api/usuarios/login/',
            {'email': usuario.email, 'password': self.password},
            format='json',
        )

        response = self.client.get(
            '/api/usuarios/usuarios/',
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_usuario_no_consulta_otra_unidad_educativa(self):
        colegio = Colegio.objects.create(nombre='Colegio JWT Tenant')
        propia = UnidadEducativa.objects.create(
            codigo_sie='JWT-UNIDAD-A', turno='TARDE', nombre='Unidad A', colegio=colegio,
        )
        ajena = UnidadEducativa.objects.create(
            codigo_sie='JWT-UNIDAD-B', turno='MAÑANA', nombre='Unidad B', colegio=colegio,
        )
        rol, _ = Rol.objects.get_or_create(nombre='Tutor')
        usuario = Usuario.objects.create_user(
            ci='JWT-TENANT', email='tenant@example.com', nombre='Usuario',
            apellido='Tenant', username='usuario_tenant', password=self.password,
            rol=rol, unidad=propia,
        )
        from .models import PermisoRol
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='unidad-educativa')
        accion, _ = Accion.objects.get_or_create(nombre='listar')
        PermisoRol.objects.get_or_create(rol=rol, modelo=modelo, accion=accion)
        login = self.client.post(
            '/api/usuarios/login/',
            {'email': usuario.email, 'password': self.password},
            format='json',
        )

        response = self.client.get(
            f'/api/institucion/unidades-educativas/{ajena.pk}/',
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class GestionCrudApiTests(APITestCase):
    def setUp(self):
        password = 'Clave-Segura-123'
        for nombre in ('Admin', 'Profesor', 'Tutor'):
            Rol.objects.get_or_create(nombre=nombre)
        director, _ = Puesto.objects.get_or_create(nombre='Director')
        for modelo_nombre, acciones in {
            'unidad-educativa': ('listar',),
            'usuario': ('listar',),
            'tipo-feriado': ('crear', 'editar', 'eliminar'),
            'profesor': ('crear', 'editar', 'eliminar'),
        }.items():
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=modelo_nombre)
            for accion_nombre in acciones:
                accion, _ = Accion.objects.get_or_create(nombre=accion_nombre)
                PermisoPuesto.objects.get_or_create(
                    puesto=director, modelo=modelo, accion=accion,
                )
        self.superusuario = Usuario.objects.create_superuser(
            ci='ADMIN-CRUD-001', email='admin-crud@example.com', nombre='Admin',
            apellido='CRUD', username='admin_crud', fecha_nacimiento='1990-01-01',
            password=password,
        )
        login = self.client.post(
            '/api/usuarios/login/',
            {'email': self.superusuario.email, 'password': password},
            format='json',
        )
        self.auth = {'HTTP_AUTHORIZATION': f"Bearer {login.data['access']}"}

    def request(self, method, url, data=None, expected=status.HTTP_200_OK):
        response = getattr(self.client, method)(url, data or {}, format='json', **self.auth)
        self.assertEqual(response.status_code, expected, response.data)
        return response

    def test_crud_de_los_modulos_administrativos(self):
        colegio = self.request('post', '/api/institucion/colegios/', {
            'nombre': 'Don Bosco Test', 'direccion': 'Calle 1', 'telefono': '70000000',
            'email': 'colegio@example.com', 'sitio_web': 'https://example.com',
        }, status.HTTP_201_CREATED).data
        self.request('patch', f"/api/institucion/colegios/{colegio['id']}/", {
            'telefono': '71111111',
        })

        unidad = self.request('post', '/api/institucion/unidades-educativas/', {
            'nombre': 'Unidad Central', 'codigo_sie': 'SIE-CRUD-01', 'turno': 'TARDE',
            'nivel': 'Primaria', 'colegio_id': colegio['id'],
        }, status.HTTP_201_CREATED).data

        roles_respuesta = self.request('get', '/api/usuarios/roles/').data
        roles = {rol['nombre']: rol for rol in roles_respuesta}

        grado = self.request('post', '/api/academico/grados/', {
            'unidad_educativa': unidad['id'], 'nivel_educativo': 'PRI', 'numero': 1,
        }, status.HTTP_201_CREATED).data
        paralelo = self.request('post', '/api/academico/paralelos/', {
            'grado_id': grado['id'], 'letra': 'A',
        }, status.HTTP_201_CREATED).data
        curso = self.request('post', '/api/academico/cursos/', {
            'paralelo_id': paralelo['id'], 'nombre': 'Primero A',
        }, status.HTTP_201_CREATED).data

        def crear_usuario(ci, username, email, rol_nombre, nombre, **perfil):
            return self.request('post', '/api/usuarios/usuarios/', {
                'ci': ci, 'username': username, 'email': email, 'nombre': nombre,
                'apellido': 'Prueba', 'password': 'Temporal-123', 'sexo': 'M',
                'rol_id': roles[rol_nombre]['id'], 'unidad_id': unidad['id'], **perfil,
            }, status.HTTP_201_CREATED).data

        docente_usuario = crear_usuario(
            'CI-DOC-CRUD', 'docente_crud', 'docente-crud@example.com',
            'Profesor', 'Docente', curso_ids=[curso['id']],
        )
        tutor_usuario = crear_usuario(
            'CI-TUT-CRUD', 'tutor_crud', 'tutor-crud@example.com',
            'Tutor', 'Tutor', parentesco='TUT',
        )
        self.request('patch', f"/api/usuarios/usuarios/{docente_usuario['id']}/", {'telefono': '72222222'})

        profesor = {'id': docente_usuario['id']}
        self.request('patch', f"/api/personal/profesores/{profesor['id']}/", {'estado': False})
        self.request('patch', f"/api/academico/cursos/{curso['id']}/", {'nombre': 'Primero A actualizado'})

        calendario = self.request('post', '/api/calendario/calendarios/', {
            'unidad_educativa': unidad['id'], 'año': 2026,
            'fecha_inicio': '2026-02-01', 'fecha_fin': '2026-11-30', 'activo': True,
        }, status.HTTP_201_CREATED).data
        periodo = self.request('post', '/api/calendario/periodos/', {
            'calendario': calendario['id'], 'tipo_division': 'TRI', 'nombre': 'Primer trimestre',
            'fecha_inicio': '2026-02-01', 'fecha_fin': '2026-05-15', 'estado': 'PLA',
        }, status.HTTP_201_CREATED).data
        tipo_feriado = self.request('post', '/api/calendario/tipos-feriado/', {
            'nombre': 'Institucional CRUD', 'descripcion': 'Prueba', 'es_nacional': False,
        }, status.HTTP_201_CREATED).data
        feriado = self.request('post', '/api/calendario/feriados/', {
            'calendario': calendario['id'], 'tipo': tipo_feriado['id'],
            'nombre': 'Aniversario', 'fecha': '2026-06-01',
        }, status.HTTP_201_CREATED).data

        estudiante = self.request('post', '/api/estudiantes/estudiantes/crear/', {
            'nuevo_estudiante': {
                'nombre': 'Nuevo', 'apellido': 'Estudiante', 'ci': 'CI-NUEVO-CRUD',
                'email': 'nuevo-estudiante@example.com', 'sexo': 'M',
                'username': 'nuevo_estudiante_crud', 'password': 'Temporal-123',
            },
            'rude': 'RUDE-CRUD-001',
            'estado': True, 'curso_id': curso['id'], 'unidad_id': unidad['id'],
        }, status.HTTP_201_CREATED).data
        tutor = self.request('get', f"/api/estudiantes/tutores/{tutor_usuario['id']}/").data
        relacion = self.request('post', '/api/estudiantes/relaciones/crear/', {
            'tutor_id': tutor['usuario']['id'], 'estudiante_id': estudiante['usuario']['id'],
            'es_principal': True,
        }, status.HTTP_201_CREATED).data

        self.request('delete', f"/api/estudiantes/relaciones/{relacion['id']}/eliminar/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/estudiantes/tutores/{tutor['usuario']['id']}/eliminar/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/estudiantes/estudiantes/{estudiante['usuario']['id']}/eliminar/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/usuarios/usuarios/{estudiante['usuario']['id']}/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/calendario/feriados/{feriado['id']}/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/calendario/periodos/{periodo['id']}/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/calendario/tipos-feriado/{tipo_feriado['id']}/", expected=status.HTTP_204_NO_CONTENT)
        from aplicaciones.academico.models import ConfiguracionEvaluacion, DimensionEvaluacion
        configuraciones = ConfiguracionEvaluacion.objects.filter(
            calendario_academico_id=calendario['id'],
        )
        DimensionEvaluacion.objects.filter(configuracion__in=configuraciones).delete()
        configuraciones.delete()
        self.request('delete', f"/api/calendario/calendarios/{calendario['id']}/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/academico/cursos/{curso['id']}/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/academico/paralelos/{paralelo['id']}/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/academico/grados/{grado['id']}/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/personal/profesores/{profesor['id']}/", expected=status.HTTP_204_NO_CONTENT)
        for usuario in (tutor_usuario,):
            self.request('delete', f"/api/usuarios/usuarios/{usuario['id']}/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/institucion/unidades-educativas/{unidad['id']}/", expected=status.HTTP_204_NO_CONTENT)
        self.request('delete', f"/api/institucion/colegios/{colegio['id']}/", expected=status.HTTP_204_NO_CONTENT)

    def test_admin_se_crea_con_puesto_unidad_y_permisos_saas(self):
        colegio = self.request('post', '/api/institucion/colegios/', {
            'nombre': 'Colegio Tenant A', 'direccion': 'A', 'telefono': '70000001',
        }, status.HTTP_201_CREATED).data
        unidad = self.request('post', '/api/institucion/unidades-educativas/', {
            'nombre': 'Unidad Tenant A', 'codigo_sie': 'TENANT-A', 'turno': 'TARDE',
            'colegio_id': colegio['id'],
        }, status.HTTP_201_CREATED).data
        colegio_b = self.request('post', '/api/institucion/colegios/', {
            'nombre': 'Colegio Tenant B', 'direccion': 'B', 'telefono': '70000002',
        }, status.HTTP_201_CREATED).data
        self.request('post', '/api/institucion/unidades-educativas/', {
            'nombre': 'Unidad Tenant B', 'codigo_sie': 'TENANT-B', 'turno': 'TARDE',
            'colegio_id': colegio_b['id'],
        }, status.HTTP_201_CREATED)

        roles = {item['nombre']: item for item in self.request('get', '/api/usuarios/roles/').data}
        puestos = {item['nombre']: item for item in self.request('get', '/api/usuarios/puestos/').data}
        director = self.request('post', '/api/usuarios/usuarios/', {
            'ci': 'CI-DIRECTOR', 'username': 'director_test', 'email': 'director@example.com',
            'nombre': 'Director', 'apellido': 'Prueba', 'password': 'Temporal-123',
            'sexo': 'M', 'rol_id': roles['Admin']['id'], 'colegio_id': colegio['id'],
            'puesto_id': puestos['Director']['id'],
        }, status.HTTP_201_CREATED).data
        self.assertIsNone(director['unidad'])
        self.assertEqual(director['colegio']['id'], colegio['id'])
        self.assertEqual(director['alcance']['tipo'], 'COLEGIO')
        self.assertEqual(director['perfil']['puesto']['nombre'], 'Director')

        login = self.client.post('/api/usuarios/login/', {
            'email': 'director@example.com', 'password': 'Temporal-123',
        }, format='json')
        auth_director = {'HTTP_AUTHORIZATION': f"Bearer {login.data['access']}"}
        unidades = self.client.get('/api/institucion/unidades-educativas/', **auth_director)
        self.assertEqual(unidades.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in unidades.data['results']], [unidad['id']])
        usuarios = self.client.get('/api/usuarios/usuarios/', **auth_director)
        self.assertEqual(usuarios.status_code, status.HTTP_200_OK)
        self.assertEqual({item['id'] for item in usuarios.data}, {director['id']})

        tipo_feriado = self.client.post('/api/calendario/tipos-feriado/', {
            'nombre': 'Feriado de Dirección', 'descripcion': 'Creado por Director',
            'es_nacional': False,
        }, format='json', **auth_director)
        self.assertEqual(tipo_feriado.status_code, status.HTTP_201_CREATED, tipo_feriado.data)
        tipo_id = tipo_feriado.data['id']
        editado = self.client.patch(
            f'/api/calendario/tipos-feriado/{tipo_id}/',
            {'descripcion': 'Actualizado por Director'}, format='json', **auth_director,
        )
        self.assertEqual(editado.status_code, status.HTTP_200_OK, editado.data)

        from aplicaciones.academico.models import Curso, Grado, Paralelo
        from aplicaciones.personal.models import Profesor

        grado = Grado.objects.create(
            unidad_educativa_id=unidad['id'], nivel_educativo='PRI', numero=2,
        )
        paralelo = Paralelo.objects.create(grado=grado, letra='A')
        curso = Curso.objects.create(paralelo=paralelo, nombre='Segundo A')
        docente = self.client.post('/api/personal/profesores/', {
            'ci': 'CI-DOC-DIRECTOR', 'username': 'docente_director',
            'email': 'docente-director@example.com', 'nombre': 'Docente',
            'apellido': 'Desde Director', 'password': 'Temporal-123', 'sexo': 'F',
            'unidad_id': unidad['id'], 'curso_ids': [], 'estado': True,
        }, format='json', **auth_director)
        self.assertEqual(docente.status_code, status.HTTP_201_CREATED, docente.data)
        docente_id = docente.data['id']
        profesor = Profesor.objects.select_related('usuario').get(usuario_id=docente_id)
        self.assertEqual(profesor.usuario.rol.nombre, 'Profesor')
        self.assertEqual(profesor.usuario.unidad_id, unidad['id'])
        self.assertFalse(profesor.cursos_tutorados.exists())
        self.assertTrue(profesor.usuario.check_password('Temporal-123'))

        actualizado = self.client.patch(
            f'/api/personal/profesores/{docente_id}/',
            {'telefono': '76543210', 'estado': False, 'curso_ids': [curso.pk]},
            format='json', **auth_director,
        )
        self.assertEqual(actualizado.status_code, status.HTTP_200_OK, actualizado.data)
        profesor.refresh_from_db()
        profesor.usuario.refresh_from_db()
        self.assertFalse(profesor.estado)
        self.assertEqual(profesor.usuario.telefono, '76543210')
        self.assertEqual(list(profesor.cursos_tutorados.values_list('pk', flat=True)), [curso.pk])

        eliminado = self.client.delete(
            f'/api/personal/profesores/{docente_id}/', **auth_director
        )
        self.assertEqual(eliminado.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Usuario.objects.filter(pk=docente_id).exists())
        borrado_feriado = self.client.delete(
            f'/api/calendario/tipos-feriado/{tipo_id}/', **auth_director
        )
        self.assertEqual(borrado_feriado.status_code, status.HTTP_204_NO_CONTENT)

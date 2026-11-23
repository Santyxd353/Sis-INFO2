from datetime import time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import zipfile

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from aplicaciones.usuarios.models import Admin, EventoAuditoria, Puesto, Rol, Usuario
from aplicaciones.institucion.models import Colegio, UnidadEducativa
from .models import ConfiguracionRespaldo, Respaldo
from .servicios import encolar, ejecutar_pendiente, programar_si_corresponde


class RespaldosTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_superuser(ci='BACK-SUP', email='back-admin@example.test', username='back-admin', nombre='Admin', apellido='Back', password='Clave-Segura-123')
        rol, _ = Rol.objects.get_or_create(nombre='Tutor')
        cls.user = Usuario.objects.create_user(ci='BACK-USER', email='back-user@example.test', username='back-user', nombre='User', apellido='Back', password='Clave-Segura-123', rol=rol)

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings_override = override_settings(RESPALDOS_ROOT=Path(self.tmp.name) / 'respaldos', MEDIA_ROOT=Path(self.tmp.name) / 'media', REPORTES_PRIVATE_ROOT=Path(self.tmp.name) / 'reportes')
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.client.force_authenticate(self.admin)

    def test_permiso_y_cola_no_duplicada(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/respaldos/').status_code, 403)
        self.assertEqual(self.client.post('/api/respaldos/').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/respaldos/').status_code, 401)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post('/api/respaldos/').status_code, 202)
        self.assertEqual(self.client.post('/api/respaldos/').status_code, 409)
        self.assertEqual(Respaldo.objects.count(), 1)
        self.assertTrue(EventoAuditoria.objects.filter(entidad='RESPALDO', accion='CREAR').exists())

    def test_completado_descarga_y_archivos(self):
        media = Path(self.tmp.name) / 'media'; media.mkdir(); (media / 'documento.txt').write_text('prueba')
        response = self.client.post('/api/respaldos/')
        def dump(args, stdout, **kwargs):
            stdout.write(b'fake-postgres-dump')
            return type('Resultado', (), {'returncode': 0})()
        with patch('aplicaciones.respaldos.servicios.subprocess.run', side_effect=dump):
            ejecutar_pendiente()
        registro = Respaldo.objects.get(pk=response.data['id'])
        self.assertEqual(registro.estado, 'COMPLETADO')
        self.assertEqual(len(registro.sha256), 64)
        with zipfile.ZipFile(Path(self.tmp.name) / 'respaldos' / registro.archivo) as archivo:
            self.assertEqual(archivo.read('base.dump'), b'fake-postgres-dump')
            self.assertEqual(archivo.read('media/documento.txt'), b'prueba')
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(f'/api/respaldos/{registro.pk}/descargar/').status_code, 403)
        self.client.force_authenticate(self.admin)
        descarga = self.client.get(f'/api/respaldos/{registro.pk}/descargar/')
        self.assertEqual(descarga.status_code, 200)
        self.assertTrue(b''.join(descarga.streaming_content).startswith(b'PK'))
        self.assertTrue(EventoAuditoria.objects.filter(entidad='RESPALDO', accion='EXPORTAR').exists())

    def test_error_y_descarga_inexistente(self):
        response = self.client.post('/api/respaldos/')
        with patch('aplicaciones.respaldos.servicios.subprocess.run', side_effect=FileNotFoundError('pg_dump')):
            ejecutar_pendiente()
        registro = Respaldo.objects.get(pk=response.data['id'])
        self.assertEqual(registro.estado, 'FALLIDO')
        self.assertEqual(self.client.get(f'/api/respaldos/{registro.pk}/descargar/').status_code, 404)
        self.assertEqual(self.client.post('/api/respaldos/').status_code, 202)

    def test_ruta_alterada_no_se_descarga_y_configuracion_protegida(self):
        registro = Respaldo.objects.create(origen='MANUAL', estado='COMPLETADO', archivo='../secreto.zip')
        self.assertEqual(self.client.get(f'/api/respaldos/{registro.pk}/descargar/').status_code, 404)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/respaldos/configuracion/').status_code, 403)
        self.assertEqual(self.client.put('/api/respaldos/configuracion/', {'activo': True, 'hora': '01:00', 'zona_horaria': 'UTC'}, format='json').status_code, 403)

    def test_pg_dump_fallido_no_publica_copia(self):
        registro = Respaldo.objects.create(origen='MANUAL')
        with patch('aplicaciones.respaldos.servicios.subprocess.run', return_value=type('Resultado', (), {'returncode': 1})()):
            ejecutar_pendiente()
        registro.refresh_from_db()
        self.assertEqual(registro.estado, 'FALLIDO')
        self.assertEqual(registro.archivo, '')
        self.assertEqual(list((Path(self.tmp.name) / 'respaldos').glob('*.zip')), [])

    def test_programacion_una_vez_por_dia_y_zona_valida(self):
        response = self.client.put('/api/respaldos/configuracion/', {'activo': True, 'hora': '00:00', 'zona_horaria': 'invalida'}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.put('/api/respaldos/configuracion/', {'activo': True, 'hora': '00:00', 'zona_horaria': 'America/La_Paz'}, format='json')
        self.assertEqual(response.status_code, 200)
        programar_si_corresponde()
        registro = Respaldo.objects.get()
        self.assertEqual(registro.origen, 'PROGRAMADO')
        registro.estado = 'COMPLETADO'; registro.save()
        programar_si_corresponde()
        self.assertEqual(Respaldo.objects.count(), 1)
        config = ConfiguracionRespaldo.objects.get(pk=1)
        config.ultima_fecha_programada = timezone.localdate() - timedelta(days=2)
        config.hora = time(23, 59, 59); config.save()
        with patch('aplicaciones.respaldos.servicios.timezone.now', return_value=timezone.datetime(2026, 1, 1, 12, 0, tzinfo=timezone.get_default_timezone())):
            programar_si_corresponde()
        self.assertEqual(Respaldo.objects.count(), 1)

    def test_estado_procesador_heartbeat_reciente_y_vencido(self):
        self.assertEqual(self.client.get('/api/respaldos/estado-procesador/').data['estado'], 'NO_DISPONIBLE')
        marca = Path(self.tmp.name) / 'respaldos' / '.worker-heartbeat'
        marca.parent.mkdir(parents=True, exist_ok=True)
        marca.write_text(timezone.now().isoformat(), encoding='ascii')
        self.assertEqual(self.client.get('/api/respaldos/estado-procesador/').data['estado'], 'DISPONIBLE')
        marca.write_text((timezone.now() - timedelta(minutes=5)).isoformat(), encoding='ascii')
        self.assertEqual(self.client.get('/api/respaldos/estado-procesador/').data['estado'], 'NO_DISPONIBLE')
    def test_alcances_y_aislamiento_del_director(self):
        colegio_a = Colegio.objects.create(nombre='Colegio A', direccion='A', telefono='1')
        colegio_b = Colegio.objects.create(nombre='Colegio B', direccion='B', telefono='2')
        unidad = UnidadEducativa.objects.create(colegio=colegio_a, codigo_sie='SIE-A', turno='MAÑANA', nombre='Unidad A')
        rol, _ = Rol.objects.get_or_create(nombre='Admin')
        puesto, _ = Puesto.objects.get_or_create(nombre='Director')
        director = Usuario.objects.create_user(ci='DIR-A', email='dir-a@example.test', username='dir-a', nombre='Dir', apellido='A', password='Clave-Segura-123', rol=rol, unidad=unidad)
        Admin.objects.create(usuario=director, puesto=puesto, colegio=colegio_a, unidad=unidad)
        self.client.force_authenticate(self.admin)
        global_response = self.client.post('/api/respaldos/', {'alcance': 'GLOBAL'}, format='json')
        self.assertEqual(global_response.status_code, 202)
        Respaldo.objects.filter(alcance='GLOBAL').update(estado='COMPLETADO')
        colegio_response = self.client.post('/api/respaldos/', {'alcance': 'COLEGIO', 'colegio': colegio_b.pk}, format='json')
        self.assertEqual(colegio_response.status_code, 202)
        self.client.force_authenticate(director)
        self.assertEqual(self.client.post('/api/respaldos/', {'alcance': 'GLOBAL'}, format='json').status_code, 403)
        own = self.client.post('/api/respaldos/', {'alcance': 'COLEGIO'}, format='json')
        self.assertEqual(own.status_code, 202)
        self.assertEqual(own.data['colegio'], colegio_a.pk)
        self.assertEqual(self.client.post('/api/respaldos/', {'alcance': 'COLEGIO', 'colegio': colegio_b.pk}, format='json').status_code, 403)
        self.assertEqual(self.client.get(f"/api/respaldos/{colegio_response.data['id']}/").status_code, 404)

    def test_exportacion_logica_filtra_colegio_y_publica_manifiesto(self):
        colegio = Colegio.objects.create(nombre='Colegio lógico', direccion='A', telefono='1')
        UnidadEducativa.objects.create(colegio=colegio, codigo_sie='SIE-LOG', turno='MAÃ‘ANA', nombre='Unidad lógica')
        registro = encolar('MANUAL', self.admin, alcance='COLEGIO', colegio=colegio)
        ejecutar_pendiente()
        registro.refresh_from_db()
        self.assertEqual(registro.estado, 'COMPLETADO')
        with zipfile.ZipFile(Path(self.tmp.name) / 'respaldos' / registro.archivo) as archivo:
            manifiesto = __import__('json').loads(archivo.read('manifest.json'))
            self.assertIn('LEEME.txt', archivo.namelist())
            self.assertIn('checksums.json', archivo.namelist())
            contenidos = [archivo.read(c['archivo']).decode('utf-8') for c in manifiesto['componentes']]
        self.assertEqual(manifiesto['alcance'], 'COLEGIO')
        self.assertEqual(manifiesto['colegio_id'], colegio.pk)
        self.assertGreaterEqual(len(manifiesto['componentes']), 2)
        self.assertTrue(any(str(colegio.pk) in contenido for contenido in contenidos))

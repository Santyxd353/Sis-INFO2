"""Run through manage.py shell against an isolated, freshly migrated preflight DB."""
import secrets
from urllib.parse import urlsplit

from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from aplicaciones.academico.models import ResultadoTrimestral
from aplicaciones.usuarios.hu_test_support import SchoolFixture

assert settings.DATABASES['default']['NAME'].startswith('gestion_escolar_check_')
SchoolFixture.setUpTestData()
fixture = SchoolFixture
host = settings.ALLOWED_HOSTS[0]
client = APIClient(HTTP_HOST=host, HTTP_X_FORWARDED_PROTO='https')


def login(user):
    password = secrets.token_urlsafe(24)
    user.set_password(password)
    user.save(update_fields=['password'])
    result = client.post('/api/usuarios/login/', {'username': user.username, 'password': password},
                         format='json', secure=True)
    assert result.status_code == 200, result.status_code
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + result.data['access'])


def get(url, status=200, **params):
    result = client.get(url, params, secure=True)
    assert result.status_code == status, (url, result.status_code)
    if url.startswith('/api/portal/'):
        assert 'no-store' in result['Cache-Control']
    return result.data


ResultadoTrimestral.objects.create(historial_inscripcion=fixture.enrollment, materia=fixture.subject,
    periodo=fixture.period, resultado=40, condicion='REPROBADO', calculado_at=timezone.now())
login(fixture.director)
panel = get('/api/portal/panel-director/', unidad_educativa=fixture.unit.pk)
assert panel['indicadores']['estudiantes_activos'] == 1
assert panel['indicadores']['promedio'] == 40
get('/api/portal/panel-director/', 404, unidad_educativa=fixture.other_unit.pk)
result = client.post('/api/comunicacion/comunicados/', {
    'titulo': 'Comunicado de validación', 'cuerpo': 'Datos sintéticos del entorno temporal.',
    'unidad_educativa': fixture.unit.pk, 'curso': fixture.course.pk,
    'prioridad': 'NORMAL', 'requiere_confirmacion': True,
}, format='json', secure=True)
assert result.status_code == 201, result.status_code
announcement = result.data['id']
result = client.post(f'/api/comunicacion/comunicados/{announcement}/publicar/', {}, format='json', secure=True)
assert result.status_code == 200, result.status_code
login(fixture.tutor_user)
family = get('/api/portal/familia/', estudiante=fixture.student.pk, calendario_academico=fixture.calendar.pk)
assert family['seleccionado'] == fixture.student.pk
assert family['notas'][0]['periodos'][0]['nota'] == '40.00'
assert family['comunicados'][0]['id'] == announcement
assert family['notificaciones']['no_leidas'] >= 2
assert family['pagos']['disponible'] is False
get('/api/portal/familia/', 404, estudiante=99999999)
get('/api/portal/panel-director/', 403)
print('PORTAL_SMOKE_OK: real JWT, family, director, tenant, grades, communications, alerts, no-store.')


def post(url, status=200, **datos):
    result = client.post(url, datos, format='json', secure=True)
    assert result.status_code == status, (url, result.status_code, result.data)
    return result.data


planes = '/api/finanzas/planes-pago/'
obligaciones = '/api/finanzas/obligaciones/'
solicitudes = '/api/finanzas/solicitudes-qr/'
login(fixture.director)
plan = post(planes, 201, unidad_educativa=fixture.unit.pk, calendario_academico=fixture.calendar.pk,
            nombre='Pensión de validación', monto_total='100.00', numero_cuotas=1)['id']
post(f'{planes}{plan}/generar-cuotas/', fecha_primer_vencimiento=fixture.calendar.fecha_inicio.isoformat())
post(f'{planes}{plan}/activar/')
post(f'{planes}{plan}/asignar/', curso=fixture.course.pk)
login(fixture.tutor_user)
cuota = get(obligaciones, estudiante=fixture.student.pk)['results'][0]['id']
with override_settings(FINANZAS_QR_DEMO_COLEGIO_IDS=[fixture.school.pk]):
    solicitud = post(solicitudes, 201, estudiante=fixture.student.pk, obligaciones=[cuota])
    assert solicitud['simulado'] and solicitud['estado'] == 'PENDIENTE'
    qr_url = urlsplit(solicitud['qr_url'])
    assert qr_url.scheme == 'https' and qr_url.hostname == host
    imagen = client.get(qr_url.path, secure=True)
    assert (imagen.status_code, imagen['Content-Type']) == (200, 'image/png')
    confirmar = f"{solicitudes}{solicitud['id']}/simular-cobro/"
    post(confirmar, 403)
    login(fixture.director)
    assert post(confirmar)['estado'] == 'PAGADA'
login(fixture.tutor_user)
avisos = get('/api/finanzas/avisos/', tipo='PAGO')
assert avisos['count'] == 1
assert get(obligaciones, estudiante=fixture.student.pk)['results'][0]['estado'] == 'PAGADA'
print('FINANZAS_SMOKE_OK: pensión, QR simulado, permiso de confirmación y aviso familiar.')

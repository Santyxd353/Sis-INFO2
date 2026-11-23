"""Cliente de Vendis; las credenciales permanecen en el servidor."""
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from rest_framework.exceptions import APIException


class PasarelaNoDisponible(APIException):
    status_code = 503
    default_detail = 'La pasarela QR no está disponible. Inténtelo más tarde.'


def _configuracion():
    base = settings.VENDIS_API_BASE_URL.rstrip('/')
    expected = {'sandbox': 'qr-dev.cobranza.emizor.com', 'production': 'vendis.cobrosqr.com'}
    parsed = urlparse(base)
    if (not settings.VENDIS_API_KEY or not settings.VENDIS_BUSINESS_CODE
            or parsed.scheme != 'https' or parsed.hostname != expected.get(settings.VENDIS_ENV)
            or parsed.username or parsed.password or parsed.port or parsed.path or parsed.query or parsed.fragment):
        raise PasarelaNoDisponible('La pasarela QR no está configurada correctamente.')
    return base


def configurado():
    try:
        _configuracion()
    except PasarelaNoDisponible:
        return False
    return True


def _request(method, path, **kwargs):
    try:
        response = requests.request(method, _configuracion() + path, headers={
            'X-API-KEY': settings.VENDIS_API_KEY, 'Accept': 'application/json',
        }, timeout=15, allow_redirects=False, **kwargs)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get('success') is not True or not isinstance(result.get('data'), dict):
            raise ValueError('Respuesta inválida')
        return result['data']
    except (requests.RequestException, ValueError):
        raise PasarelaNoDisponible() from None


def generar(monto, referencia, vencimiento, concepto='Suscripcion'):
    code = settings.VENDIS_BUSINESS_CODE
    data = _request('POST', '/api/v1/devices/simple-qr/generate', json={
        'business_code': int(code) if code.isdigit() else code,
        'amount': float(monto), 'modify_amount': False, 'is_multi_use': False,
        'qr_expiration': vencimiento.astimezone(ZoneInfo('America/La_Paz')).strftime('%Y-%m-%d %H:%M:%S'),
        'description': f'{concepto} {referencia}'[:50],
    })
    qr_id, url = str(data.get('qr_id') or ''), data.get('qr_url')
    if not qr_id or len(qr_id) > 100 or not isinstance(url, str) or len(url) > 2048:
        raise PasarelaNoDisponible('La pasarela devolvió un QR inválido; requiere revisión.')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise PasarelaNoDisponible('La pasarela devolvió un QR inválido; requiere revisión.')
    return qr_id, url


def consultar(qr_id):
    return _request('GET', '/api/v1/devices/simple-qr/get/' + quote(qr_id, safe=''))

"""Acceso a la pasarela QR para pensiones.

Delega en Vendis salvo para los colegios de demostración configurados o al
usar VENDIS_ENV=simulado con DEBUG activo.
"""
import io
import uuid

from django.conf import settings
from django.core.cache import cache

from aplicaciones.suscripciones import vendis

from .fechas import ZONA_BOLIVIA

PREFIJO_SIMULADO = 'SIM-'


def simulada(colegio_id=None):
    return (settings.DEBUG and settings.VENDIS_ENV == 'simulado'
            or colegio_id in settings.FINANZAS_QR_DEMO_COLEGIO_IDS)


def es_qr_simulado(qr_id):
    return bool(qr_id and qr_id.startswith(PREFIJO_SIMULADO))


def generar(monto, referencia, vencimiento, *, colegio_id):
    if simulada(colegio_id):
        qr_id = f'{PREFIJO_SIMULADO}{uuid.uuid4().hex[:20]}'
        return qr_id, f'/api/finanzas/qr-simulado/{qr_id}.png'
    return vendis.generar(monto, referencia, vencimiento, concepto='Pension')


def consultar(qr_id):
    if es_qr_simulado(qr_id):
        return cache.get(f'qr-simulado:{qr_id}') or {'status': 'PENDIENTE'}
    return vendis.consultar(qr_id)


def marcar_cobro_simulado(qr_id, monto, fecha):
    cache.set(f'qr-simulado:{qr_id}', {
        'status': 'PAGADO',
        'payments': [{
            'payment_amount': str(monto),
            'payment_date': fecha.astimezone(ZONA_BOLIVIA).strftime('%Y-%m-%d %H:%M:%S'),
        }],
    }, timeout=24 * 3600)


def imagen_qr_simulado(qr_id):
    from PIL import Image
    from reportlab.graphics.barcode import qrencoder

    codigo = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.M)
    codigo.addData(f'PAGO SIMULADO {qr_id}')
    codigo.make()
    lado, margen = codigo.getModuleCount(), 4
    imagen = Image.new('1', (lado + 2 * margen, lado + 2 * margen), 1)
    for fila in range(lado):
        for columna in range(lado):
            if codigo.isDark(fila, columna):
                imagen.putpixel((columna + margen, fila + margen), 0)
    imagen = imagen.resize((imagen.width * 8, imagen.height * 8), Image.NEAREST)
    salida = io.BytesIO()
    imagen.save(salida, 'PNG')
    return salida.getvalue()

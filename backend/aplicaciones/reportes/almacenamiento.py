"""Almacenamiento local privado, sin URL pública para reportes."""
import os
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage


def almacenamiento():
    raiz = Path(settings.REPORTES_PRIVATE_ROOT).resolve()
    for publica in (settings.MEDIA_ROOT, settings.STATIC_ROOT):
        if publica:
            publica = Path(publica).resolve()
            if raiz == publica or publica in raiz.parents or raiz in publica.parents:
                raise ImproperlyConfigured('El almacenamiento de reportes debe estar separado de media y static.')
    return FileSystemStorage(location=str(raiz), base_url=None)


def validar_clave(clave):
    if not isinstance(clave, str) or not re.fullmatch(r'[a-f0-9]{32}\.(csv|pdf)', clave):
        raise ValueError('Clave de reporte inválida.')
    return clave


def guardar_archivo(contenido, extension):
    if extension not in ('csv', 'pdf'):
        raise ValueError('Formato inválido.')
    storage = almacenamiento()
    raiz = Path(storage.location)
    raiz.mkdir(parents=True, exist_ok=True)
    clave = f'{uuid4().hex}.{extension}'
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(dir=raiz, prefix='.reporte-', delete=False) as archivo:
            temporal = archivo.name
            archivo.write(contenido)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, storage.path(clave))
        return clave
    finally:
        if temporal and os.path.exists(temporal):
            os.unlink(temporal)


def eliminar_archivo(clave):
    almacenamiento().delete(validar_clave(clave))

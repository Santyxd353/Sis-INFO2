import hashlib
import json
import logging
import os
import subprocess
import tempfile
import zipfile
import shutil
import time
from django.db import close_old_connections, connection
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from .models import ConfiguracionRespaldo, Respaldo
from .colegio import generar_respaldo_colegio
from aplicaciones.usuarios.auditoria import registrar_evento

logger = logging.getLogger(__name__)


def raiz_segura():
    raiz = Path(settings.RESPALDOS_ROOT).resolve()
    for valor in (settings.MEDIA_ROOT, settings.STATIC_ROOT, settings.REPORTES_PRIVATE_ROOT):
        if valor:
            otra = Path(valor).resolve()
            if raiz == otra or raiz in otra.parents or otra in raiz.parents:
                raise ImproperlyConfigured('La carpeta de respaldos debe estar separada de media, static y reportes.')
    raiz.mkdir(parents=True, exist_ok=True, mode=0o700)
    return raiz


def registrar_heartbeat():
    try:
        ruta = raiz_segura() / '.worker-heartbeat'
        temporal = ruta.with_suffix('.tmp')
        temporal.write_text(timezone.now().isoformat(), encoding='ascii')
        os.replace(temporal, ruta)
    except Exception:
        logger.exception('No se pudo actualizar el heartbeat del procesador de respaldos')


def pg_dump_disponible():
    valor = str(getattr(settings, 'PG_DUMP_PATH', '') or '')
    return bool(valor) and (Path(valor).is_file() if Path(valor).is_absolute() else shutil.which(valor))


def worker_loop(stop_event=None):
    """Ciclo continuo usado por el worker de producción y por runserver local."""
    close_old_connections()
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [1826217429])
        if not cursor.fetchone()[0]:
            logger.warning('Ya hay un procesador de respaldos activo.')
            return
    try:
        Respaldo.objects.filter(estado='EJECUTANDO').update(
            estado='FALLIDO', finalizado_at=timezone.now(),
            error='La ejecución anterior se interrumpió. Solicite un nuevo respaldo.',
        )
        while stop_event is None or not stop_event.is_set():
            registrar_heartbeat()
            try:
                programar_si_corresponde()
                while Respaldo.objects.filter(estado='PENDIENTE').exists():
                    ejecutar_pendiente()
            except Exception:
                logger.exception('Error al procesar la cola de respaldos')
            close_old_connections()
            if stop_event is None:
                time.sleep(15)
            elif stop_event.wait(15):
                break
    finally:
        close_old_connections()
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [1826217429])


def encolar(origen, usuario=None, alcance='GLOBAL', colegio=None):
    if alcance not in {Respaldo.ALCANCE_GLOBAL, Respaldo.ALCANCE_COLEGIO}:
        raise ValueError('Alcance de respaldo no valido.')
    if alcance == Respaldo.ALCANCE_GLOBAL and colegio is not None:
        raise ValueError('Un respaldo global no admite colegio.')
    if alcance == Respaldo.ALCANCE_COLEGIO and colegio is None:
        raise ValueError('El respaldo de colegio requiere colegio.')
    with transaction.atomic():
        ConfiguracionRespaldo.objects.get_or_create(pk=1)
        ConfiguracionRespaldo.objects.select_for_update().get(pk=1)
        filtros = {'alcance': alcance, 'estado__in': ['PENDIENTE', 'EJECUTANDO']}
        filtros['colegio' if alcance == Respaldo.ALCANCE_COLEGIO else 'colegio__isnull'] = colegio if alcance == Respaldo.ALCANCE_COLEGIO else True
        if Respaldo.objects.filter(**filtros).exists():
            return None
        return Respaldo.objects.create(origen=origen, solicitado_por=usuario, alcance=alcance, colegio=colegio)


def programar_si_corresponde():
    with transaction.atomic():
        ConfiguracionRespaldo.objects.get_or_create(pk=1)
        config = ConfiguracionRespaldo.objects.select_for_update().get(pk=1)
        ahora = timezone.now().astimezone(ZoneInfo(config.zona_horaria))
        if not config.activo or ahora.time().replace(tzinfo=None) < config.hora or config.ultima_fecha_programada == ahora.date():
            return
        if Respaldo.objects.filter(alcance='GLOBAL', estado__in=['PENDIENTE', 'EJECUTANDO']).exists():
            return
        Respaldo.objects.create(origen='PROGRAMADO', alcance='GLOBAL')
        config.ultima_fecha_programada = ahora.date()
        config.save(update_fields=['ultima_fecha_programada'])


def ejecutar_pendiente():
    with transaction.atomic():
        respaldo = Respaldo.objects.select_for_update().filter(estado='PENDIENTE').first()
        if not respaldo:
            return False
        respaldo.estado = 'EJECUTANDO'
        respaldo.iniciado_at = timezone.now()
        respaldo.save(update_fields=['estado', 'iniciado_at'])
    temporal = None
    destino = None
    try:
        raiz = raiz_segura()
        db = settings.DATABASES['default']
        if db['ENGINE'] != 'django.db.backends.postgresql':
            raise RuntimeError('Solo se admite PostgreSQL.')
        variables = os.environ.copy()
        variables['PGPASSWORD'] = str(db.get('PASSWORD') or '')
        variables['PGCONNECT_TIMEOUT'] = '10'
        args = [settings.PG_DUMP_PATH, '--format=custom', '--no-owner', '--no-privileges', '--host', str(db.get('HOST') or 'localhost'), '--port', str(db.get('PORT') or '5432'), '--username', str(db.get('USER') or ''), '--dbname', str(db['NAME'])]
        with tempfile.TemporaryDirectory(prefix='.trabajo-', dir=raiz) as carpeta:
            carpeta = Path(carpeta)
            if respaldo.alcance == Respaldo.ALCANCE_COLEGIO:
                temporal = carpeta / 'respaldo.edubackup'
                manifest = generar_respaldo_colegio(respaldo.colegio_id, temporal, respaldo.pk)
                digest = hashlib.sha256(temporal.read_bytes()).hexdigest()
                tamano = temporal.stat().st_size
                nombre = f'respaldo_colegio_{respaldo.colegio_id}_{timezone.now():%Y%m%d_%H%M}.edubackup'
                destino = raiz / nombre
                os.replace(temporal, destino)
                Respaldo.objects.filter(pk=respaldo.pk).update(
                    estado='COMPLETADO', finalizado_at=timezone.now(), archivo=nombre,
                    tamano=tamano, sha256=digest, version_formato=2,
                    metadatos={**manifest, 'registros_totales': sum(c['registros'] for c in manifest.get('componentes', [])), 'cantidad_componentes': len(manifest.get('componentes', []))},
                )
                return True
            dump = carpeta / 'base.dump'
            if not pg_dump_disponible():
                raise RuntimeError('configuracion_pg_dump')
            with dump.open('wb') as salida:
                resultado = subprocess.run(args, stdout=salida, stderr=subprocess.PIPE, env=variables, timeout=3600, check=False)
            if resultado.returncode != 0:
                raise RuntimeError('pg_dump no pudo generar la copia de la base de datos.')
            temporal = carpeta / 'respaldo.zip'
            with zipfile.ZipFile(temporal, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archivo:
                archivo.write(dump, 'base.dump')
                archivo.writestr('manifest.json', json.dumps({'version_formato': 1, 'tipo': 'postgresql+archivos', 'alcance': 'GLOBAL', 'respaldo_id': str(respaldo.pk), 'creado_utc': timezone.now().isoformat(), 'componentes': ['base.dump', 'media', 'reportes'], 'advertencia': 'Los archivos no son una instantánea transaccional de la base.'}, ensure_ascii=False))
                for nombre, origen in [('media', settings.MEDIA_ROOT), ('reportes', settings.REPORTES_PRIVATE_ROOT)]:
                    base = Path(origen)
                    if not base.exists():
                        continue
                    if base.is_symlink():
                        raise RuntimeError('El directorio de archivos no puede ser un enlace simbólico.')
                    for archivo_path in base.rglob('*'):
                        if archivo_path.is_symlink():
                            raise RuntimeError('Se encontró un enlace simbólico en los archivos.')
                        if archivo_path.is_file():
                            archivo.write(archivo_path, f'{nombre}/{archivo_path.relative_to(base).as_posix()}')
            digest = hashlib.sha256()
            with temporal.open('rb') as archivo:
                for bloque in iter(lambda: archivo.read(1024 * 1024), b''):
                    digest.update(bloque)
            tamano = temporal.stat().st_size
            nombre = f'respaldo_global_{timezone.now():%Y%m%d_%H%M}.edubackup'
            destino = raiz / nombre
            os.replace(temporal, destino)
        Respaldo.objects.filter(pk=respaldo.pk).update(estado='COMPLETADO', finalizado_at=timezone.now(), archivo=nombre, tamano=tamano, sha256=digest.hexdigest())
        return True
    except Exception:
        logger.exception('Falló la ejecución del respaldo %s', respaldo.pk)
        if destino and destino.is_file():
            destino.unlink()
        exc = locals().get('exc')
        mensaje = 'El respaldo global no pudo generarse por una configuración del servidor.' if respaldo.alcance == Respaldo.ALCANCE_GLOBAL and str(exc) == 'configuracion_pg_dump' else 'No se pudo generar el respaldo. Inténtelo nuevamente o contacte al administrador técnico.'
        Respaldo.objects.filter(pk=respaldo.pk).update(estado='FALLIDO', finalizado_at=timezone.now(), error=mensaje)
        try:
            registrar_evento(
                accion='EXPORTAR', entidad='RESPALDO', usuario=respaldo.solicitado_por,
                entidad_id=str(respaldo.pk), colegio=respaldo.colegio,
                cambios={'resultado': 'fallido', 'alcance': respaldo.alcance},
            )
        except Exception:
            logger.exception('No se pudo registrar la auditoría del fallo de respaldo %s', respaldo.pk)

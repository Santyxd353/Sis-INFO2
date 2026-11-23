"""runserver local con worker de respaldos controlado por autoreload."""
import logging
import os
import threading

from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import Command as StaticRunserverCommand

from aplicaciones.respaldos.servicios import worker_loop

logger = logging.getLogger(__name__)


class Command(StaticRunserverCommand):
    def inner_run(self, *args, **options):
        use_reloader = options.get('use_reloader', True)
        es_hijo_autoreload = os.environ.get('RUN_MAIN') == 'true'
        iniciar = bool(settings.DEBUG and (not use_reloader or es_hijo_autoreload))
        detenido = threading.Event()
        worker = None
        if iniciar:
            worker = threading.Thread(target=worker_loop, args=(detenido,), name='respaldos-worker-local', daemon=True)
            worker.start()
            logger.info('Worker local de respaldos iniciado junto a runserver.')
        try:
            return super().inner_run(*args, **options)
        finally:
            if worker:
                detenido.set()
                worker.join(timeout=20)
                logger.info('Worker local de respaldos detenido junto a runserver.')

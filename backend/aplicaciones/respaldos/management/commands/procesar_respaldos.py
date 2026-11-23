import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone
from aplicaciones.respaldos.models import Respaldo
from aplicaciones.respaldos.servicios import ejecutar_pendiente, programar_si_corresponde, registrar_heartbeat

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Procesa la cola de respaldos y comprueba la programación diariamente.'

    def add_arguments(self, parser):
        parser.add_argument('--una-vez', action='store_true')

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [1826217429])
            if not cursor.fetchone()[0]:
                raise CommandError('Ya hay un procesador de respaldos activo.')
        try:
            Respaldo.objects.filter(estado='EJECUTANDO').update(estado='FALLIDO', finalizado_at=timezone.now(), error='La ejecución anterior se interrumpió. Solicite un nuevo respaldo.')
            while True:
                registrar_heartbeat()
                try:
                    programar_si_corresponde()
                    # Drena toda la cola en orden; un fallo queda marcado y no
                    # impide que la siguiente solicitud sea procesada.
                    while Respaldo.objects.filter(estado='PENDIENTE').exists():
                        ejecutar_pendiente()
                except Exception:
                    logger.exception('Error al procesar la cola de respaldos')
                    if options['una_vez']:
                        raise
                if options['una_vez']:
                    break
                time.sleep(15)
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [1826217429])

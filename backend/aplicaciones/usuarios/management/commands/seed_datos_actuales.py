"""Carga el fixture JSON embebido en SEEDER_DATOS_ACTUALES.md.

El comando es explícito porque el archivo contiene una fotografía de datos
locales. No se ejecuta automáticamente durante migrate ni durante el arranque
del servidor.
"""

import json
import os
import tempfile
from pathlib import Path

from django.core.management import BaseCommand, CommandError, call_command


class Command(BaseCommand):
    help = 'Carga los datos seed documentados en SEEDER_DATOS_ACTUALES.md.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--archivo',
            default=None,
            help='Ruta alternativa al Markdown que contiene el bloque JSON.',
        )
        parser.add_argument(
            '--confirmar-datos-locales',
            action='store_true',
            help='Confirma que se desea cargar la fotografía de datos actual.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Valida el bloque JSON sin escribir en la base de datos.',
        )

    def handle(self, *args, **options):
        archivo = Path(options['archivo']) if options['archivo'] else Path(settings_base()) / 'SEEDER_DATOS_ACTUALES.md'
        if not archivo.exists():
            raise CommandError(f'No existe el seeder: {archivo}')
        if not options['confirmar_datos_locales']:
            raise CommandError(
                'La carga de datos actuales requiere --confirmar-datos-locales. '
                'No se ejecuta automáticamente para evitar duplicar datos reales.'
            )
        try:
            contenido = archivo.read_text(encoding='utf-8')
            bloque = contenido.split('```json\n', 1)[1].rsplit('\n```', 1)[0]
            datos = json.loads(bloque)
        except (OSError, IndexError, json.JSONDecodeError) as exc:
            raise CommandError(f'El seeder no contiene un bloque JSON válido: {exc}') from exc
        if not isinstance(datos, list):
            raise CommandError('El fixture del seeder debe ser una lista JSON.')
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f'Seeder válido: {len(datos)} objetos; no se modificó la base de datos.'
            ))
            return

        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', suffix='.json', delete=False,
        ) as temporal:
            json.dump(datos, temporal, ensure_ascii=False)
            ruta_temporal = temporal.name
        try:
            call_command('loaddata', ruta_temporal, verbosity=options.get('verbosity', 1))
        finally:
            try:
                os.unlink(ruta_temporal)
            except OSError:
                pass
        self.stdout.write(self.style.SUCCESS(
            f'Seeder cargado correctamente: {len(datos)} objetos.'
        ))


def settings_base():
    from django.conf import settings
    return settings.BASE_DIR

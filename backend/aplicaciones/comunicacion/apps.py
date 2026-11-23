from django.apps import AppConfig


class ComunicacionConfig(AppConfig):
    name = 'aplicaciones.comunicacion'

    def ready(self):
        from . import signals  # noqa: F401

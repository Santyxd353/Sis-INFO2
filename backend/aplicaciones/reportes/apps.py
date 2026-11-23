from django.apps import AppConfig


class ReportesConfig(AppConfig):
    name = 'aplicaciones.reportes'
    label = 'reportes'

    def ready(self):
        from . import signals  # noqa: F401

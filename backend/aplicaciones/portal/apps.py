from django.apps import AppConfig


class PortalConfig(AppConfig):
    name = 'aplicaciones.portal'

    def ready(self):
        from . import signals  # noqa: F401

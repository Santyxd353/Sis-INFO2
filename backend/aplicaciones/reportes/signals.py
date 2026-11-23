from django.db.models.signals import post_save
from django.dispatch import receiver

from aplicaciones.usuarios.models import Puesto
from .permisos import otorgar_permisos_director, otorgar_permisos_secretaria


@receiver(post_save, sender=Puesto)
def asignar_permisos_operativos_a_secretaria(sender, instance, created, **kwargs):
    if created:
        otorgar_permisos_secretaria(instance)
        otorgar_permisos_director(instance)

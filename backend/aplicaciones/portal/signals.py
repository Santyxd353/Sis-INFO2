from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from aplicaciones.usuarios.models import Accion, ModeloPermitido, PermisoPuesto, Puesto
from aplicaciones.usuarios.tenancy import normalizar_nombre


def grant(puesto):
    model, _ = ModeloPermitido.objects.get_or_create(nombre='portal-panel')
    action, _ = Accion.objects.get_or_create(nombre='listar')
    PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=model, accion=action)


@receiver(post_save, sender=Puesto)
def new_director(sender, instance, created, raw=False, **kwargs):
    if created and not raw and normalizar_nombre(instance.nombre) == 'director':
        grant(instance)


@receiver(post_migrate)
def seed_permissions(sender, **kwargs):
    if sender.name == 'aplicaciones.portal':
        for puesto in Puesto.objects.all():
            if normalizar_nombre(puesto.nombre) == 'director':
                grant(puesto)

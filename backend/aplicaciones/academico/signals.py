from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from aplicaciones.calendario.models import CalendarioAcademico

from .models import ConfiguracionEvaluacion, DimensionEvaluacion

# HU-15: niveles que se evalúan con el esquema numérico Ser/Saber/Hacer/
# Decidir/Autoevaluación (Ley N.º 070). Educación Inicial no usa esta escala.
NIVELES_EVALUACION_NUMERICA = ('PRI', 'SEC')

# Puntajes oficiales por dimensión (código, nombre, ponderación, orden).
DIMENSIONES_OFICIALES = (
    ('SER', 'Ser', 10, 1),
    ('SABER', 'Saber', 35, 2),
    ('HACER', 'Hacer', 35, 3),
    ('DECIDIR', 'Decidir', 10, 4),
    ('AUTOEVAL', 'Autoevaluación', 10, 5),
)


@receiver(post_save, sender=CalendarioAcademico)
def crear_configuracion_evaluacion_default(sender, instance, created, **kwargs):
    """Al crear una gestión académica, carga la configuración de evaluación
    y las 5 dimensiones oficiales por defecto (10/35/35/10/10) para los
    niveles con escala numérica."""
    if not created:
        return
    with transaction.atomic():
        for nivel in NIVELES_EVALUACION_NUMERICA:
            configuracion, nueva = ConfiguracionEvaluacion.objects.get_or_create(
                calendario_academico=instance,
                nivel=nivel,
                defaults={
                    'nota_minima': 0,
                    'nota_maxima': 100,
                    'nota_aprobacion': 51,
                    'decimales': 0,
                    'regla_redondeo': ConfiguracionEvaluacion.ReglaRedondeo.NORMAL,
                },
            )
            if nueva:
                DimensionEvaluacion.objects.bulk_create([
                    DimensionEvaluacion(
                        configuracion=configuracion, codigo=codigo, nombre=nombre,
                        ponderacion=ponderacion, orden=orden,
                    )
                    for codigo, nombre, ponderacion, orden in DIMENSIONES_OFICIALES
                ])

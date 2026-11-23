from decimal import Decimal

from django.db import models
from django.conf import settings
from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.academico.models import Materia, Curso
from aplicaciones.calendario.models import Periodo
from aplicaciones.institucion.models import UnidadEducativa


class ConfiguracionRiesgo(models.Model):
    """Umbrales configurables para detectar riesgo académico y de inasistencia."""

    unidad = models.ForeignKey(
        UnidadEducativa, on_delete=models.CASCADE, null=True, blank=True,
        related_name='configuraciones_riesgo',
    )
    umbral_rendimiento = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('70.00'),
        help_text='Promedio mínimo aceptable (por debajo = bajo rendimiento).',
    )
    umbral_riesgo_alto = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('51.00'),
        help_text='Promedio por debajo del cual el riesgo es alto (alerta roja).',
    )
    umbral_inasistencia = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('15.00'),
        help_text='% de inasistencia a partir del cual es recurrente.',
    )
    porcentaje_minimo_asistencia = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('85.00'),
        help_text='% de asistencia mínimo esperado.',
    )
    activo = models.BooleanField(default=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Riesgo'
        verbose_name_plural = 'Configuraciones de Riesgo'
        ordering = ['unidad_id']

    def __str__(self):
        return f'Configuración riesgo (unidad {self.unidad_id or "global"})'

    @classmethod
    def get_config(cls, unidad=None):
        qs = cls.objects.filter(activo=True)
        return (
            qs.filter(unidad=unidad).first()
            or qs.filter(unidad__isnull=True).first()
            or cls.objects.create()
        )


class HistorialEstudiante(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.PROTECT, related_name='historial')
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, related_name='historiales')
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name='historiales')
    promedio = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('estudiante', 'periodo', 'curso')
        ordering = ['-periodo__fecha_inicio']

    def __str__(self):
        return f'Historial {self.estudiante} - {self.periodo}'


class Nota(models.Model):
    TIPOS = (
        ('P1', 'Parcial 1'),
        ('P2', 'Parcial 2'),
        ('PF', 'Final'),
        ('EX', 'Extra'),
    )
    historial = models.ForeignKey(HistorialEstudiante, on_delete=models.CASCADE, related_name='notas')
    materia = models.ForeignKey(Materia, on_delete=models.PROTECT, related_name='notas')
    tipo_evaluacion = models.CharField(max_length=2, choices=TIPOS)
    nota = models.DecimalField(max_digits=4, decimal_places=2)
    ponderacion = models.DecimalField(max_digits=4, decimal_places=2, default=1.00)

    class Meta:
        unique_together = ('historial', 'materia', 'tipo_evaluacion')
        ordering = ['materia__nombre']

    def __str__(self):
        return f'{self.materia} - {self.nota}'


class RiesgoAcademico(models.Model):
    NIVELES = (
        ('B', 'Bajo'),
        ('M', 'Medio'),
        ('A', 'Alto'),
    )
    estudiante = models.ForeignKey(Estudiante, on_delete=models.PROTECT, related_name='riesgos')
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, related_name='riesgos')
    nivel = models.CharField(max_length=1, choices=NIVELES, default='M')
    motivo = models.TextField()
    acciones_propuestas = models.TextField(blank=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='riesgos_gestionados')
    activo = models.BooleanField(default=True)
    fecha_evaluacion = models.DateField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_evaluacion']

    def __str__(self):
        return f'Riesgo {self.get_nivel_display()} - {self.estudiante}'

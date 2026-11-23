from django.db import models
from django.conf import settings
from aplicaciones.academico.models import MateriaCurso
from aplicaciones.calendario.models import Periodo
from aplicaciones.estudiantes.models import Estudiante


class RegistroAsistencia(models.Model):
    """Cabecera de asistencia de una asignación (materia-curso) en una fecha."""

    asignacion = models.ForeignKey(
        MateriaCurso,
        on_delete=models.PROTECT,
        related_name='registros_asistencia',
    )
    fecha = models.DateField()
    periodo = models.ForeignKey(
        Periodo, on_delete=models.PROTECT, null=True, blank=True,
        related_name='registros_asistencia',
    )
    observacion = models.CharField(max_length=255, blank=True)
    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='registros_asistencia_docente',
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Registro de Asistencia'
        verbose_name_plural = 'Registros de Asistencia'
        unique_together = ('fecha', 'asignacion')
        ordering = ['-fecha']

    @property
    def curso(self):
        return self.asignacion.curso

    @property
    def materia(self):
        return self.asignacion.materia

    def __str__(self):
        return f'Asistencia {self.fecha} - {self.asignacion}'


class DetalleAsistencia(models.Model):
    ESTADOS = (
        ('P', 'Presente'),
        ('A', 'Ausente'),
        ('T', 'Tarde'),
        ('L', 'Licencia'),
    )
    registro = models.ForeignKey(
        RegistroAsistencia, on_delete=models.CASCADE, related_name='detalles',
    )
    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.PROTECT, related_name='detalles_asistencia',
    )
    estado = models.CharField(max_length=1, choices=ESTADOS, default='A')
    observacion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'Detalle de Asistencia'
        verbose_name_plural = 'Detalles de Asistencia'
        unique_together = ('registro', 'estudiante')
        ordering = ['estudiante__usuario__apellido', 'estudiante__usuario__nombre']

    def __str__(self):
        return f'{self.estudiante} - {self.get_estado_display()}'

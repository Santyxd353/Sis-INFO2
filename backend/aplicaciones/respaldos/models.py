import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class ConfiguracionRespaldo(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    activo = models.BooleanField(default=False)
    hora = models.TimeField(default='02:00')
    zona_horaria = models.CharField(max_length=64, default='America/La_Paz')
    ultima_fecha_programada = models.DateField(null=True, blank=True)


class Respaldo(models.Model):
    ALCANCE_GLOBAL = 'GLOBAL'
    ALCANCE_COLEGIO = 'COLEGIO'
    ALCANCE_CHOICES = ((ALCANCE_GLOBAL, 'Global'), (ALCANCE_COLEGIO, 'Colegio'))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    origen = models.CharField(max_length=12, choices=[('MANUAL', 'Manual'), ('PROGRAMADO', 'Programado')])
    estado = models.CharField(max_length=16, default='PENDIENTE')
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    solicitado_at = models.DateTimeField(auto_now_add=True)
    iniciado_at = models.DateTimeField(null=True, blank=True)
    finalizado_at = models.DateTimeField(null=True, blank=True)
    archivo = models.CharField(max_length=64, blank=True)
    tamano = models.BigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    error = models.CharField(max_length=300, blank=True)
    alcance = models.CharField(max_length=10, choices=ALCANCE_CHOICES, default=ALCANCE_GLOBAL)
    colegio = models.ForeignKey(
        'institucion.Colegio', null=True, blank=True, on_delete=models.PROTECT,
        related_name='respaldos',
    )
    version_formato = models.PositiveSmallIntegerField(default=1)
    metadatos = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-solicitado_at']
        constraints = [
            models.CheckConstraint(
                condition=(Q(alcance='GLOBAL', colegio__isnull=True) | Q(alcance='COLEGIO', colegio__isnull=False)),
                name='ck_respaldo_alcance_colegio',
            ),
            models.UniqueConstraint(
                fields=['estado'], condition=Q(alcance='GLOBAL', estado='PENDIENTE'),
                name='un_respaldo_global_pendiente',
            ),
            models.UniqueConstraint(
                fields=['estado'], condition=Q(alcance='GLOBAL', estado='EJECUTANDO'),
                name='un_respaldo_global_ejecutando',
            ),
            models.UniqueConstraint(
                fields=['colegio', 'estado'], condition=Q(alcance='COLEGIO', estado='PENDIENTE'),
                name='un_respaldo_colegio_pendiente',
            ),
            models.UniqueConstraint(
                fields=['colegio', 'estado'], condition=Q(alcance='COLEGIO', estado='EJECUTANDO'),
                name='un_respaldo_colegio_ejecutando',
            ),
        ]
        indexes = [
            models.Index(fields=['alcance', 'estado', '-solicitado_at'], name='ix_respaldo_alcance_estado'),
            models.Index(fields=['colegio', 'estado', '-solicitado_at'], name='ix_respaldo_colegio_estado'),
        ]

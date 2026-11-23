import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .fuentes import _FUENTES
from .seguridad import tiene_permiso, validar_contexto, validar_json


class SinBorradoQuerySet(models.QuerySet):
    def delete(self):
        raise ValidationError('Los reportes no se eliminan físicamente.')


class Validado(models.Model):
    objects = SinBorradoQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Los reportes no se eliminan físicamente.')


class ReporteDefinicion(Validado):
    id = models.BigAutoField(primary_key=True)
    colegio = models.ForeignKey('institucion.Colegio', on_delete=models.PROTECT)
    unidad_educativa = models.ForeignKey('institucion.UnidadEducativa', on_delete=models.PROTECT, null=True, blank=True)
    propietario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, default='')
    tipo = models.CharField(max_length=20, choices=[('OPERATIVO', 'Operativo'), ('QBE', 'QBE')])
    codigo_fuente = models.CharField(max_length=50)
    version_esquema = models.PositiveIntegerField(default=1)
    especificacion = models.JSONField(default=dict, blank=True)
    estado = models.CharField(max_length=20, choices=[('ACTIVO', 'Activo'), ('ARCHIVADO', 'Archivado')], default='ACTIVO')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archivado_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'reportes_reporte_definicion'
        constraints = [
            models.UniqueConstraint(Lower('nombre'), 'colegio', 'propietario', condition=Q(estado='ACTIVO'), name='uq_rep_def_nombre_activo'),
            models.CheckConstraint(condition=Q(tipo__in=['OPERATIVO', 'QBE']), name='ck_rep_def_tipo'),
            models.CheckConstraint(condition=Q(estado='ACTIVO', archivado_at__isnull=True) | Q(estado='ARCHIVADO', archivado_at__isnull=False), name='ck_rep_def_archivo'),
        ]

    def clean(self):
        super().clean()
        self.nombre = ' '.join((self.nombre or '').split())
        if not self.nombre:
            raise ValidationError({'nombre': 'El nombre es obligatorio.'})
        if self.tipo != 'QBE' and self.codigo_fuente not in _FUENTES:
            raise ValidationError({'codigo_fuente': 'Fuente no permitida.'})
        validar_json(self.especificacion)
        if not isinstance(self.especificacion, dict):
            raise ValidationError({'especificacion': 'Se requiere un objeto.'})
        if self.tipo == 'QBE':
            from .qbe import fuente_qbe, validar_qbe
            fuente = fuente_qbe(self.codigo_fuente)
            if fuente is None:
                raise ValidationError({'codigo_fuente': 'Fuente QBE no permitida.'})
            self.especificacion = validar_qbe(self.especificacion, fuente)
        if self.unidad_educativa_id and self.unidad_educativa.colegio_id != self.colegio_id:
            raise ValidationError({'unidad_educativa': 'La unidad no pertenece al colegio.'})
        if self.propietario_id and self.colegio_id:
            if not tiene_permiso(self.propietario, 'reporte-definicion', 'crear'):
                raise ValidationError({'propietario': 'El propietario no tiene permiso explícito.'})
            try:
                validar_contexto(self.propietario, self.colegio_id, self.unidad_educativa_id)
            except PermissionDenied as exc:
                raise ValidationError({'propietario': 'Propietario fuera del contexto institucional.'}) from exc

    def archivar(self):
        self.estado = 'ARCHIVADO'
        self.archivado_at = timezone.now()
        self.save(update_fields=['estado', 'archivado_at', 'updated_at'])


class EjecucionReporte(Validado):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definicion = models.ForeignKey(ReporteDefinicion, on_delete=models.PROTECT, null=True, blank=True)
    colegio = models.ForeignKey('institucion.Colegio', on_delete=models.PROTECT)
    unidad_educativa = models.ForeignKey('institucion.UnidadEducativa', on_delete=models.PROTECT, null=True, blank=True)
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    actor_snapshot = models.JSONField(default=dict, blank=True)
    tipo = models.CharField(max_length=20, choices=[(x, x) for x in ('OPERATIVO', 'QBE', 'ANALITICO', 'VOZ')])
    estado = models.CharField(max_length=20, choices=[(x, x) for x in ('PENDIENTE', 'EN_PROCESO', 'COMPLETADO', 'ERROR', 'CANCELADO')], default='PENDIENTE')
    fuente_codigo = models.CharField(max_length=50)
    fuente_version = models.PositiveIntegerField(default=1)
    parametros_sanitizados = models.JSONField(default=dict, blank=True)
    filas_resultado = models.PositiveIntegerField(null=True, blank=True)
    formato = models.CharField(max_length=10, choices=[(x, x) for x in ('PDF', 'CSV', 'JSON')], null=True, blank=True)
    archivo_referencia = models.CharField(max_length=500, null=True, blank=True)
    archivo_mime = models.CharField(max_length=100, null=True, blank=True)
    archivo_checksum = models.CharField(max_length=128, null=True, blank=True)
    archivo_tamano = models.PositiveBigIntegerField(null=True, blank=True)
    error_sanitizado = models.CharField(max_length=80, null=True, blank=True)
    correlacion = models.UUIDField(default=uuid.uuid4)
    iniciada_at = models.DateTimeField(default=timezone.now)
    finalizada_at = models.DateTimeField(null=True, blank=True)
    archivado_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reportes_ejecucion_reporte'
        indexes = [models.Index(fields=['colegio', 'estado', 'created_at'], name='ix_rep_ej_colegio_estado'), models.Index(fields=['unidad_educativa', 'created_at'], name='ix_rep_ej_unidad_fecha'), models.Index(fields=['solicitante', 'created_at'], name='ix_rep_ej_actor_fecha'), models.Index(fields=['tipo', 'created_at'], name='ix_rep_ej_tipo_fecha'), models.Index(fields=['correlacion'], name='ix_rep_ej_correlacion')]
        constraints = [models.CheckConstraint(condition=~Q(estado='COMPLETADO') | Q(finalizada_at__isnull=False), name='ck_rep_ej_completado'), models.CheckConstraint(condition=~Q(estado='ERROR') | (Q(error_sanitizado__isnull=False) & ~Q(error_sanitizado='')), name='ck_rep_ej_error')]

    def clean(self):
        super().clean()
        if self.unidad_educativa_id and self.unidad_educativa.colegio_id != self.colegio_id:
            raise ValidationError({'unidad_educativa': 'La unidad no pertenece al colegio.'})
        if self.definicion_id and (self.definicion.colegio_id != self.colegio_id or (self.definicion.unidad_educativa_id and self.definicion.unidad_educativa_id != self.unidad_educativa_id)):
            raise ValidationError({'definicion': 'La definición no pertenece al contexto.'})
        from .qbe import fuente_qbe
        if self.fuente_codigo not in _FUENTES and not (self.tipo == 'QBE' and fuente_qbe(self.fuente_codigo)) and not (self.tipo == 'ANALITICO' and self.fuente_codigo == 'ANALITICA'):
            raise ValidationError({'fuente_codigo': 'Fuente no permitida.'})
        for campo in ('actor_snapshot', 'parametros_sanitizados'):
            valor = getattr(self, campo)
            if not isinstance(valor, dict):
                raise ValidationError({campo: 'Se requiere un objeto.'})
            validar_json(valor)
        if set(self.actor_snapshot) - {'usuario_id'} or ('usuario_id' in self.actor_snapshot and not isinstance(self.actor_snapshot['usuario_id'], int)):
            raise ValidationError({'actor_snapshot': 'Solo se admite el identificador del actor.'})
        if self.estado == 'COMPLETADO' and not self.finalizada_at:
            raise ValidationError({'finalizada_at': 'Requerida al completar.'})
        if self.estado == 'ERROR' and not self.error_sanitizado:
            raise ValidationError({'error_sanitizado': 'Se requiere un código de error.'})
        if self.error_sanitizado and not re.fullmatch(r'[A-Z0-9_]{1,80}', self.error_sanitizado):
            raise ValidationError({'error_sanitizado': 'Use solo un código de error sanitizado.'})
        if self.error_sanitizado and any(x in self.error_sanitizado.upper() for x in ('PASSWORD', 'TOKEN', 'SECRET', 'SQL', 'TRACEBACK', 'AUDIO')):
            raise ValidationError({'error_sanitizado': 'El código contiene información prohibida.'})

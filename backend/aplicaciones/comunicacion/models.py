from django.conf import settings
from django.db import models


class TipoAviso(models.TextChoices):
    COMUNICADO = 'COMUNICADO', 'Comunicado'
    FALTA = 'FALTA', 'Falta'
    ATRASO = 'ATRASO', 'Atraso'
    NOTA_BAJA = 'NOTA_BAJA', 'Nota baja'
    PAGO = 'PAGO', 'Pago'
    CONTINGENCIA = 'CONTINGENCIA', 'Contingencia'
    CITACION = 'CITACION', 'Citación'
    BOLETIN = 'BOLETIN', 'Boletín'


def preferencias_predeterminadas():
    return dict.fromkeys(TipoAviso.values, True)


class Comunicado(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        ARCHIVADO = 'ARCHIVADO', 'Archivado'

    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    unidad_educativa = models.ForeignKey('institucion.UnidadEducativa', on_delete=models.PROTECT)
    curso = models.ForeignKey('academico.Curso', null=True, blank=True, on_delete=models.PROTECT)
    prioridad = models.CharField(max_length=10, choices=[('NORMAL', 'Normal'), ('URGENTE', 'Urgente')], default='NORMAL')
    requiere_confirmacion = models.BooleanField(default=False)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    publicado_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(
            condition=(models.Q(estado='BORRADOR', publicado_at__isnull=True)
                       | models.Q(estado__in=['PUBLICADO', 'ARCHIVADO'], publicado_at__isnull=False)),
            name='ck_comunicado_publicacion',
        )]


class DestinatarioComunicado(models.Model):
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name='destinatarios')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    leido_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['comunicado', 'usuario'], name='uq_comunicado_destinatario')]


class Aviso(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='avisos_comunicacion')
    unidad_educativa = models.ForeignKey('institucion.UnidadEducativa', on_delete=models.PROTECT)
    tipo = models.CharField(max_length=15, choices=TipoAviso.choices)
    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    clave_evento = models.CharField(max_length=200)
    comunicado = models.ForeignKey(Comunicado, on_delete=models.PROTECT, null=True, blank=True)
    datos = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    leida_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['unidad_educativa', 'clave_evento', 'usuario'], name='uq_aviso_evento_usuario')]
        indexes = [models.Index(fields=['usuario', 'leida_at', '-created_at'], name='ix_aviso_bandeja')]


class PreferenciaNotificacion(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    categorias = models.JSONField(default=preferencias_predeterminadas)

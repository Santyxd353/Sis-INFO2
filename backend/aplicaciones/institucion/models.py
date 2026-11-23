from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.functions import Lower
from aplicaciones.usuarios.models import SuperAdmin
class Colegio(models.Model):
    class TipoSubsistema(models.TextChoices):
        FISCAL = 'FISCAL', 'Fiscal'
        PRIVADO = 'PRIVADO', 'Privado'
        CONVENIO = 'CONVENIO', 'Convenio'

    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    codigo_tenant = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        editable=False,
    )
    tipo_subsistema = models.CharField(
        max_length=12,
        choices=TipoSubsistema.choices,
        null=True,
        blank=True,
    )
    nombre = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='colegios/logos/', null=True, blank=True)
    logo_ref = models.CharField(max_length=500, null=True, blank=True)
    color_primario = models.CharField(max_length=20, null=True, blank=True)
    color_secundario = models.CharField(max_length=20, null=True, blank=True)
    zona_horaria = models.CharField(max_length=50, default='America/La_Paz')
    moneda = models.CharField(max_length=3, default='BOB')
    pais = models.CharField(max_length=2, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='')
    ciudad = models.CharField(max_length=100, blank=True, default='')
    idioma = models.CharField(max_length=10, default='es')
    razon_facturacion = models.CharField(max_length=150, blank=True, default='')
    email_facturacion = models.EmailField(blank=True, default='')
    identificacion_fiscal = models.CharField(max_length=60, blank=True, default='')
    requiere_suscripcion = models.BooleanField(default=False)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    eliminado_at = models.DateTimeField(null=True, blank=True)
    direccion = models.TextField()
    telefono = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    sitio_web = models.URLField(blank=True, null=True)
    super_admin_fk= models.ForeignKey(
        SuperAdmin,
        on_delete=models.SET_NULL,
        related_name='colegios',
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'Colegio'
        verbose_name_plural = 'Colegios'
        db_table = 'colegio'
    
    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self._state.adding and self.created_at is None:
            self.created_at = now
        self.updated_at = now
        super().save(*args, **kwargs)

class Modulo(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    nombre = models.CharField(max_length=100)
    cantidad_aulas = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    descripcion = models.TextField(blank=True, null=True)
    colegio_fk = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        related_name='modulos',
        null=True,
        blank=True
    )
    # Nullable only during the expand-contract reconciliation of legacy data.
    unidad_educativa = models.ForeignKey(
        'UnidadEducativa',
        on_delete=models.PROTECT,
        related_name='modulos_fisicos',
        null=True,
        blank=True,
    )
    pisos = models.PositiveSmallIntegerField(default=1, help_text='Número de pisos del módulo')
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    created_at = models.DateTimeField(null=True, blank=True, editable=False)
    updated_at = models.DateTimeField(null=True, blank=True, editable=False)
    eliminado_at = models.DateTimeField(null=True, blank=True)


    class Meta:
        verbose_name = 'Módulo'
        verbose_name_plural = 'Módulos'
        db_table = 'modulo'
        constraints = [
            models.UniqueConstraint(
                Lower('nombre'), 'unidad_educativa',
                condition=Q(unidad_educativa__isnull=False, estado='ACTIVO', eliminado_at__isnull=True),
                name='uq_modulo_unidad_nombre_activo_ci',
            ),
        ]
        indexes = [
            models.Index(fields=['unidad_educativa', 'estado'], name='ix_modulo_unidad_estado'),
        ]
    
    def __str__(self):
        return f"{self.nombre} ({self.cantidad_aulas} aulas, {self.pisos} pisos)"

    def clean(self):
        super().clean()
        if self.unidad_educativa_id and self.colegio_fk_id and self.unidad_educativa.colegio_id != self.colegio_fk_id:
            raise ValidationError({'colegio_fk': 'Debe coincidir con el colegio de la unidad educativa.'})

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self._state.adding and self.created_at is None:
            self.created_at = now
        self.updated_at = now
        super().save(*args, **kwargs)

class Aula(models.Model):
    TIPOS_AULA = [
        ('AUL', 'Aula Regular'),
        ('LAB', 'Laboratorio'),
        ('TAL', 'Taller'),
        ('AUD', 'Auditorio'),
        ('COM', 'Sala de Computación'),
        ('GIM', 'Gimnasio'),
        ('BIB', 'Biblioteca'),
    ]
    
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aulas'
    )
    nombre = models.CharField(max_length=50)
    capacidad = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    estado = models.BooleanField(default=True)
    
    tipo = models.CharField(
        max_length=3,
        choices=TIPOS_AULA,
        default='AUL'
    )
    equipamiento = models.TextField(blank=True, null=True)
    piso = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(null=True, blank=True, editable=False)
    updated_at = models.DateTimeField(null=True, blank=True, editable=False)
    eliminado_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Aula'
        verbose_name_plural = 'Aulas'
        db_table = 'aula'
        unique_together = ('modulo', 'nombre')
        constraints = [
            models.UniqueConstraint(
                Lower('nombre'), 'modulo',
                condition=Q(modulo__isnull=False, estado=True, eliminado_at__isnull=True),
                name='uq_aula_modulo_nombre_activo_ci',
            ),
        ]
        indexes = [
            models.Index(fields=['modulo', 'estado'], name='ix_aula_modulo_estado'),
        ]
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()}) - Módulo {self.modulo}"

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self._state.adding and self.created_at is None:
            self.created_at = now
        self.updated_at = now
        super().save(*args, **kwargs)

class UnidadEducativa(models.Model):
    TURNOS = [
        ('MAÑANA', 'Mañana'),
        ('TARDE', 'Tarde'),
        ('NOCHE', 'Noche'),
        ('COMPLETO', 'Jornada Completa'),
    ]
    
    
    codigo_sie = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código SIE'
    )
    turno = models.CharField(
        max_length=10,
        choices=TURNOS
    )
    nombre= models.CharField(max_length=100,blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    nivel = models.CharField(max_length=50,blank=True, null=True)
    codigo_interno = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )
    codigo_rue = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )
    correo = models.EmailField(
        max_length=254,
        null=True,
        blank=True
    )
    umbral_riesgo_asistencia = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True
    )
    umbral_riesgo_promedio = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True
    )
    umbral_riesgo_incidentes = models.IntegerField(
        null=True,
        blank=True
    )
    riesgo_version = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )
    sie_habilitado = models.BooleanField(default=False)
    sie_version = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )
    sie_config = models.JSONField(default=dict)
    estado = models.CharField(
        max_length=20,
        choices=[
            ('ACTIVO', 'Activo'),
            ('INACTIVO', 'Inactivo'),
        ],
        default='ACTIVO'
    )
    created_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False
    )
    updated_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False
    )
    eliminado_at = models.DateTimeField(
        null=True,
        blank=True
    )
    colegio = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        related_name='unidades_educativas',
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'Unidad Educativa'
        verbose_name_plural = 'Unidades Educativas'
        db_table = 'unidad_educativa'
    
    def __str__(self):
        return f"{self.colegio} - Turno {self.get_turno_display()}"

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self._state.adding and self.created_at is None:
            self.created_at = now
        self.updated_at = now

        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'updated_at'}

        super().save(*args, **kwargs)


class ExportacionSIE(models.Model):
    unidad_educativa = models.ForeignKey(UnidadEducativa, on_delete=models.PROTECT, related_name='exportaciones_sie')
    calendario_academico = models.ForeignKey('calendario.CalendarioAcademico', on_delete=models.PROTECT, related_name='exportaciones_sie')
    tipo = models.CharField(max_length=30)
    version = models.PositiveIntegerField()
    estado = models.CharField(max_length=20, default='PENDIENTE')
    configuracion_snapshot = models.JSONField(default=dict, blank=True)
    errores_sanitizados = models.JSONField(default=list, blank=True)
    archivo_ref = models.CharField(max_length=500, null=True, blank=True)
    archivo_mime = models.CharField(max_length=100, null=True, blank=True)
    archivo_tamano = models.BigIntegerField(null=True, blank=True)
    archivo_checksum = models.CharField(max_length=128, null=True, blank=True)
    created_by = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, related_name='exportaciones_sie_creadas', null=True, blank=True)
    created_by_snapshot = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finalizado_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sie_exportacion'
        constraints = [
            models.UniqueConstraint(fields=['unidad_educativa', 'calendario_academico', 'tipo', 'version'], name='uq_sie_exportacion_version'),
            models.CheckConstraint(condition=Q(archivo_tamano__isnull=True) | Q(archivo_tamano__gte=0), name='ck_sie_exportacion_tamano'),
            models.CheckConstraint(condition=~Q(estado='FINALIZADO') | Q(finalizado_at__isnull=False, archivo_ref__isnull=False), name='ck_sie_exportacion_finalizada'),
        ]

    def clean(self):
        super().clean()
        if self.unidad_educativa_id and self.calendario_academico_id:
            if self.calendario_academico.unidad_educativa_id != self.unidad_educativa_id:
                raise ValidationError({'calendario_academico': 'No corresponde a la unidad educativa.'})

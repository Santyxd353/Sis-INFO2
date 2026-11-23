from django.db import models
from aplicaciones.usuarios.models import Usuario
from aplicaciones.academico.models import Curso
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import F, Q

PARENTESCOS = [
    ('PAD', 'Padre'),
    ('MAD', 'Madre'),
    ('TUT', 'Tutor Legal'),
    ('HER', 'Hermano/a'),
    ('OTR', 'Otro'),
]

class Estudiante(models.Model):
    
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='estudiante'
    )
    rude = models.CharField(max_length=50, unique=True)
    estado = models.BooleanField(default=True)
    curso = models.ForeignKey(
        Curso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estudiantes'
    )
    unidad = models.ForeignKey(
        'institucion.UnidadEducativa',
        on_delete=models.PROTECT,
        related_name="estudiantes",
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'
        db_table = 'estudiante'
        ordering = ['usuario__apellido', 'usuario__nombre']
    
    def __str__(self):
        return f"{self.usuario} - {self.rude}"

class Tutor(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='tutor'
    )
    parentesco = models.CharField(
        max_length=3,
        choices=PARENTESCOS,
        default='OTR'
    )
    
    class Meta:
        verbose_name = 'Tutor'
        verbose_name_plural = 'Tutores'
        db_table = 'tutor'
        ordering = ['usuario__apellido', 'usuario__nombre']
    
    def __str__(self):
        return f"{self.usuario} ({self.get_parentesco_display()})"

class TutorEstudiante(models.Model):
    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.CASCADE,
        related_name='estudiantes'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='tutores'
    )
    fecha_asignacion = models.DateField(auto_now_add=True)
    es_principal = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Relación Tutor-Estudiante'
        verbose_name_plural = 'Relaciones Tutor-Estudiante'
        db_table = 'tutor_estudiante'
        unique_together = ('tutor', 'estudiante')
        ordering = ['-es_principal', 'fecha_asignacion']
    
    def __str__(self):
        tipo = "Principal" if self.es_principal else "Secundario"
        return f"{self.tutor} -> {self.estudiante} ({tipo})"


class HistorialInscripcion(models.Model):
    ESTADO_CHOICES = [
        ('NUEVA', 'Nueva Inscripción'),
        ('CAMBIO', 'Cambio de Curso'),
        ('RETIRADO', 'Retirado'),
        ('TRANSLADADO', 'Transladado'),
    ]
    
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='historial_inscripciones'
    )
    curso_anterior = models.ForeignKey(
        Curso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_anterior'
    )
    curso_nuevo = models.ForeignKey(
        Curso,
        on_delete=models.PROTECT,
        related_name='historial_nuevo'
    )
    unidad = models.ForeignKey(
        'institucion.UnidadEducativa',
        on_delete=models.PROTECT,
        related_name='historial_inscripciones'
    )
    tipo_movimiento = models.CharField(
        max_length=15,
        choices=ESTADO_CHOICES,
        default='NUEVA'
    )
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    usuario_registra = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inscripciones_registradas'
    )
    observaciones = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Historial de Inscripción'
        verbose_name_plural = 'Historiales de Inscripción'
        db_table = 'historial_inscripcion'
        ordering = ['-fecha_inscripcion']
        indexes = [
            models.Index(fields=['estudiante', '-fecha_inscripcion']),
            models.Index(fields=['unidad', 'curso_nuevo']),
        ]
    
    def __str__(self):
        return f"{self.estudiante.usuario} - {self.tipo_movimiento} - {self.fecha_inscripcion.date()}"


class SesionClase(models.Model):
    class Tipo(models.TextChoices):
        REGULAR = 'REGULAR', 'Regular'
        EXTRAORDINARIA = 'EXTRAORDINARIA', 'Extraordinaria'

    asignacion_docente = models.ForeignKey(
        'academico.AsignacionDocente', on_delete=models.PROTECT, related_name='sesiones',
    )
    horario_clase = models.ForeignKey(
        'academico.HorarioClase', on_delete=models.PROTECT, related_name='sesiones',
        null=True, blank=True,
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.REGULAR)
    sesion_origen = models.ForeignKey(
        'self', on_delete=models.PROTECT, related_name='sesiones_reemplazo', null=True, blank=True,
    )
    fecha = models.DateField()
    hora_inicio_real = models.TimeField(null=True, blank=True)
    hora_fin_real = models.TimeField(null=True, blank=True)
    profesor_efectivo = models.ForeignKey(
        'personal.Profesor', on_delete=models.PROTECT, related_name='sesiones_efectivas',
    )
    aula_efectiva = models.ForeignKey(
        'institucion.Aula', on_delete=models.PROTECT, related_name='sesiones_efectivas',
    )
    estado = models.CharField(max_length=20, default='PROGRAMADA')
    motivo = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='sesiones_clase_creadas', null=True, blank=True,
    )
    created_by_snapshot = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asistencia_sesion_clase'
        constraints = [
            models.CheckConstraint(
                condition=(Q(hora_inicio_real__isnull=True) | Q(hora_fin_real__isnull=True) | Q(hora_fin_real__gte=F('hora_inicio_real'))),
                name='ck_sesion_horas_reales',
            ),
            models.CheckConstraint(
                condition=~Q(sesion_origen=F('id')), name='ck_sesion_origen_distinta',
            ),
            models.UniqueConstraint(
                fields=['asignacion_docente', 'fecha', 'horario_clase'],
                condition=Q(horario_clase__isnull=False), name='uq_sesion_asignacion_fecha',
            ),
        ]


class AsistenciaEstudiante(models.Model):
    class EstadoAsistencia(models.TextChoices):
        PRESENTE = 'PRESENTE', 'Presente'
        AUSENTE = 'AUSENTE', 'Ausente'
        ATRASO = 'ATRASO', 'Atraso'
        LICENCIA = 'LICENCIA', 'Licencia'

    sesion_clase = models.ForeignKey(SesionClase, on_delete=models.PROTECT, related_name='asistencias')
    historial_inscripcion = models.ForeignKey(
        HistorialInscripcion, on_delete=models.PROTECT, related_name='asistencias',
    )
    estado_asistencia = models.CharField(max_length=20, choices=EstadoAsistencia.choices)
    observacion = models.TextField(null=True, blank=True)
    justificada = models.BooleanField(default=False)
    motivo_justificacion = models.TextField(null=True, blank=True)
    archivo_ref = models.CharField(max_length=500, null=True, blank=True)
    archivo_mime = models.CharField(max_length=100, null=True, blank=True)
    archivo_tamano = models.BigIntegerField(null=True, blank=True)
    archivo_checksum = models.CharField(max_length=128, null=True, blank=True)
    estado_aprobacion = models.CharField(max_length=20, null=True, blank=True)
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='asistencias_aprobadas', null=True, blank=True,
    )
    aprobador_snapshot = models.CharField(max_length=200, null=True, blank=True)
    aprobado_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asistencia_estudiante'
        constraints = [
            models.UniqueConstraint(
                fields=['sesion_clase', 'historial_inscripcion'], name='uq_asistencia_sesion_historial',
            ),
            models.CheckConstraint(
                condition=Q(archivo_tamano__isnull=True) | Q(archivo_tamano__gte=0),
                name='ck_asistencia_archivo_tamano',
            ),
        ]

    def clean(self):
        super().clean()
        if self.sesion_clase_id and self.historial_inscripcion_id:
            curso_sesion = self.sesion_clase.asignacion_docente.curso_id
            if self.historial_inscripcion.curso_nuevo_id != curso_sesion:
                raise ValidationError({'historial_inscripcion': 'El estudiante no pertenece al curso de la sesión.'})


class IncidenteDisciplinario(models.Model):
    historial_inscripcion = models.ForeignKey(
        HistorialInscripcion, on_delete=models.PROTECT, related_name='incidentes_disciplinarios',
    )
    fecha = models.DateTimeField()
    tipo = models.CharField(max_length=40)
    severidad = models.CharField(max_length=20)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, default='ABIERTO')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='incidentes_creados', null=True, blank=True,
    )
    created_by_snapshot = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'disciplina_incidente'
        indexes = [
            models.Index(fields=['historial_inscripcion', 'fecha'], name='ix_incidente_historial_fecha'),
            models.Index(fields=['severidad', 'estado'], name='ix_incidente_severidad_estado'),
        ]


class AccionDisciplinaria(models.Model):
    class Tipo(models.TextChoices):
        MEDIDA = 'MEDIDA', 'Medida'
        CITACION = 'CITACION', 'Citación'

    incidente = models.ForeignKey(
        IncidenteDisciplinario, on_delete=models.PROTECT, related_name='acciones',
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    tutor_estudiante = models.ForeignKey(
        TutorEstudiante, on_delete=models.PROTECT, related_name='acciones_disciplinarias',
        null=True, blank=True,
    )
    descripcion = models.TextField(null=True, blank=True)
    fecha_programada = models.DateTimeField(null=True, blank=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    resultado = models.TextField(null=True, blank=True)
    estado = models.CharField(max_length=20, default='PENDIENTE')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='acciones_disciplinarias_creadas', null=True, blank=True,
    )
    created_by_snapshot = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'disciplina_accion'
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True) | Q(fecha_inicio__isnull=True) | Q(fecha_fin__gte=F('fecha_inicio')),
                name='ck_accion_fechas',
            ),
            models.CheckConstraint(
                condition=(
                    Q(tipo='CITACION', fecha_programada__isnull=False)
                    | (
                        Q(tipo='MEDIDA')
                        & (Q(descripcion__isnull=False) | Q(fecha_inicio__isnull=False, fecha_fin__isnull=False))
                    )
                ),
                name='ck_accion_datos_tipo',
            ),
        ]

    def clean(self):
        super().clean()
        if self.tipo == self.Tipo.MEDIDA and not self.descripcion and not (self.fecha_inicio and self.fecha_fin):
            raise ValidationError('Una medida requiere descripción o rango de fechas.')
        if self.tutor_estudiante_id and self.incidente_id:
            estudiante_incidente = self.incidente.historial_inscripcion.estudiante_id
            if self.tutor_estudiante.estudiante_id != estudiante_incidente:
                raise ValidationError({'tutor_estudiante': 'El tutor no corresponde al estudiante del incidente.'})


class DocumentoAcademicoEmitido(models.Model):
    class Tipo(models.TextChoices):
        BOLETIN = 'BOLETIN', 'Boletín'
        CENTRALIZADOR = 'CENTRALIZADOR', 'Centralizador'

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    historial_inscripcion = models.ForeignKey(HistorialInscripcion, on_delete=models.PROTECT, related_name='documentos_academicos', null=True, blank=True)
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name='documentos_academicos', null=True, blank=True)
    periodo = models.ForeignKey('calendario.Periodo', on_delete=models.PROTECT, related_name='documentos_academicos', null=True, blank=True)
    calendario_academico = models.ForeignKey('calendario.CalendarioAcademico', on_delete=models.PROTECT, related_name='documentos_academicos')
    version = models.PositiveIntegerField()
    archivo_ref = models.CharField(max_length=500)
    archivo_mime = models.CharField(max_length=100)
    archivo_tamano = models.BigIntegerField()
    archivo_checksum = models.CharField(max_length=128)
    emitido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='documentos_academicos_emitidos', null=True, blank=True)
    emisor_snapshot = models.CharField(max_length=200, null=True, blank=True)
    emitido_at = models.DateTimeField()

    class Meta:
        db_table = 'reportes_documento_academico'
        constraints = [
            models.CheckConstraint(condition=Q(tipo='BOLETIN', historial_inscripcion__isnull=False, curso__isnull=True) | Q(tipo='CENTRALIZADOR', historial_inscripcion__isnull=True, curso__isnull=False), name='ck_doc_academico_tipo'),
            models.CheckConstraint(condition=Q(version__gt=0), name='ck_doc_academico_version'),
            models.CheckConstraint(condition=Q(archivo_tamano__gt=0), name='ck_doc_academico_tamano'),
            models.UniqueConstraint(fields=['historial_inscripcion', 'periodo', 'version'], condition=Q(tipo='BOLETIN', periodo__isnull=False), name='uq_boletin_trimestral'),
            models.UniqueConstraint(fields=['historial_inscripcion', 'version'], condition=Q(tipo='BOLETIN', periodo__isnull=True), name='uq_boletin_anual'),
            models.UniqueConstraint(fields=['curso', 'periodo', 'version'], condition=Q(tipo='CENTRALIZADOR', periodo__isnull=False), name='uq_centralizador_trimestral'),
            models.UniqueConstraint(fields=['curso', 'version'], condition=Q(tipo='CENTRALIZADOR', periodo__isnull=True), name='uq_centralizador_anual'),
        ]

    def clean(self):
        super().clean()
        if self.periodo_id and self.calendario_academico_id and self.periodo.calendario_id != self.calendario_academico_id:
            raise ValidationError({'periodo': 'El periodo no pertenece al calendario indicado.'})


class RiesgoAcademico(models.Model):
    historial_inscripcion = models.ForeignKey(HistorialInscripcion, on_delete=models.PROTECT, related_name='riesgos_academicos')
    tipo = models.CharField(max_length=30)
    severidad = models.CharField(max_length=20)
    valor_detectado = models.DecimalField(max_digits=7, decimal_places=2)
    umbral_aplicado = models.DecimalField(max_digits=7, decimal_places=2)
    regla_version = models.CharField(max_length=30)
    criterio = models.JSONField(default=dict)
    estado = models.CharField(max_length=20, default='ABIERTO')
    detectado_at = models.DateTimeField()
    resuelto_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reportes_riesgo_academico'
        constraints = [
            models.UniqueConstraint(fields=['historial_inscripcion', 'tipo', 'regla_version'], condition=Q(estado='ABIERTO'), name='uq_riesgo_academico_abierto'),
            models.CheckConstraint(condition=~Q(estado='RESUELTO') | Q(resuelto_at__isnull=False), name='ck_riesgo_resuelto_fecha'),
        ]

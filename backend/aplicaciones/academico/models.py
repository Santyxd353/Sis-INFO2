from django.db import models
from django.conf import settings
from aplicaciones.institucion.models import UnidadEducativa, Aula  # Asumiendo que existe esta app
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.db.models.functions import Lower



class Grado(models.Model):
    NIVELES_EDUCATIVOS = [
        ('INI', 'Educación Inicial'),
        ('PRI', 'Educación Primaria'),
        ('SEC', 'Educación Secundaria'),
    ]

    unidad_educativa = models.ForeignKey(
        UnidadEducativa,
        on_delete=models.CASCADE,
        related_name='grados'
    )
    nivel_educativo = models.CharField(
        max_length=3,
        choices=NIVELES_EDUCATIVOS
    )
    numero = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(6)],
        default=1,                          # <— aquí
        help_text="Número de grado dentro del nivel (1 a 6)"
    )

    class Meta:
        verbose_name = 'Grado'
        verbose_name_plural = 'Grados'
        db_table = 'grado'
        unique_together = ('unidad_educativa', 'nivel_educativo', 'numero')

    @property
    def nombre(self) -> str:
        if self.nivel_educativo == 'INI' and self.numero in (1, 2):
            return {1: 'Prekínder', 2: 'Kínder'}[self.numero]
        # Mapea 1→'1ro', 2→'2do', 3→'3ro', 4→'4to', 5→'5to', 6→'6to'
        sufijos = {1: 'ro',   2: 'do', 3: 'ro',
                   4: 'to',   5: 'to', 6: 'to'}
        suf = sufijos.get(self.numero, '°')
        nivel = self.get_nivel_educativo_display()
        return f"{self.numero}{suf} de {nivel}"

    def __str__(self):
        return self.nombre

class Paralelo(models.Model):
    grado = models.ForeignKey(
        Grado,
        on_delete=models.CASCADE,
        related_name='paralelos'
    )
    letra = models.CharField(max_length=1)
    # capacidad_maxima = models.PositiveIntegerField()
    
    class Meta:
        verbose_name = 'Paralelo'
        verbose_name_plural = 'Paralelos'
        db_table = 'paralelo'
        unique_together = ('grado', 'letra')
        ordering = ['letra']
    
    def __str__(self):
        return f"{self.grado} - Paralelo {self.letra}"

class Curso(models.Model):
    paralelo = models.OneToOneField(
        Paralelo,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='curso'
    )
    nombre = models.CharField(max_length=100)

    tutor = models.ForeignKey(
        'personal.Profesor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cursos_tutorados'
    )
    
    class Meta:
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'
        db_table = 'curso'
    
    def __str__(self):
        tutor_str = f" (Tutor: {self.tutor})" if self.tutor else ""
        return f"{self.nombre} - {self.paralelo}{tutor_str}"

class Materia(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    unidad_educativa = models.ForeignKey(
        UnidadEducativa, on_delete=models.PROTECT, null=True, blank=True,
        related_name='materias',
    )
    nombre = models.CharField(max_length=100)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    eliminado_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Materia'
        verbose_name_plural = 'Materias'
        db_table = 'materia'
        constraints = [
            models.UniqueConstraint(
                Lower('nombre'), 'unidad_educativa',
                condition=Q(
                    unidad_educativa__isnull=False, estado='ACTIVO', eliminado_at__isnull=True,
                ),
                name='uq_materia_unidad_nombre_activo_ci',
            ),
        ]
        indexes = [
            models.Index(fields=['unidad_educativa', 'estado'], name='ix_materia_unidad_estado'),
        ]
    
    def __str__(self):
        return self.nombre

class MateriaCurso(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='materias'
    )
    materia = models.ForeignKey(
        Materia,
        on_delete=models.CASCADE,
        related_name='cursos'
    )

    profesor = models.ForeignKey(
        'personal.Profesor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='materias_impartidas'
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    eliminado_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Materia por Curso'
        verbose_name_plural = 'Materias por Curso'
        db_table = 'materia_curso'
        unique_together = ('curso', 'materia')
        indexes = [
            models.Index(fields=['curso', 'estado'], name='ix_materia_curso_estado'),
        ]
    
    def __str__(self):
        prof = f" — Prof.: {self.profesor}" if self.profesor else ""
        return f"{self.materia} en {self.curso}{prof}"

    def clean(self):
        super().clean()
        if not self.curso_id or not self.materia_id:
            return
        unidad_curso = self.curso.paralelo.grado.unidad_educativa_id
        if self.materia.unidad_educativa_id is None:
            raise ValidationError({'materia': 'La materia histórica sin unidad no admite nuevas relaciones.'})
        if self.materia.unidad_educativa_id != unidad_curso:
            raise ValidationError({'materia': 'La materia y el curso deben pertenecer a la misma unidad educativa.'})
        if self.materia.estado != Materia.Estado.ACTIVO or self.materia.eliminado_at is not None:
            raise ValidationError({'materia': 'La materia debe estar activa.'})
    


    
class Clase(models.Model):
    # Apunta ahora a MateriaCurso en lugar de Curso
    materia_curso = models.ForeignKey(
        MateriaCurso,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='clases',
        verbose_name='Materia en Curso'
    )
    aula = models.ForeignKey(
        Aula,
        on_delete=models.CASCADE,
        related_name='clases',
        verbose_name='Aula asignada'
    )

    class Meta:
        verbose_name = 'Clase'
        verbose_name_plural = 'Clases'
        db_table = 'clase'

    def __str__(self):
        # Muestro la materia y el curso a través de la relación intermedia
        return f"{self.materia_curso.materia.nombre} en {self.materia_curso.curso.nombre} — Aula {self.aula.nombre}"


class AsignacionDocente(models.Model):
    class Tipo(models.TextChoices):
        TUTOR_CURSO = 'TUTOR_CURSO', 'Tutor de curso'
        MATERIA = 'MATERIA', 'Materia'

    tipo = models.CharField(max_length=25, choices=Tipo.choices)
    calendario_academico = models.ForeignKey(
        'calendario.CalendarioAcademico',
        on_delete=models.PROTECT,
        related_name='asignaciones_docentes',
        null=True,
        blank=True,
    )
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name='asignaciones_docentes')
    materia_curso = models.ForeignKey(
        MateriaCurso, on_delete=models.PROTECT, related_name='asignaciones_docentes',
        null=True, blank=True,
    )
    profesor = models.ForeignKey(
        'personal.Profesor', on_delete=models.PROTECT, related_name='asignaciones_docentes',
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    horas_semanales = models.PositiveSmallIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=20, default='ACTIVO')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    eliminado_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'academico_asignacion_docente'
        constraints = [
            models.CheckConstraint(
                condition=(Q(tipo='TUTOR_CURSO', materia_curso__isnull=True) | Q(tipo='MATERIA', materia_curso__isnull=False)),
                name='ck_asignacion_tipo_materia',
            ),
            models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=F('fecha_inicio')),
                name='ck_asignacion_fechas',
            ),
            models.UniqueConstraint(
                fields=['calendario_academico', 'curso'],
                condition=Q(tipo='TUTOR_CURSO', estado='ACTIVO', eliminado_at__isnull=True),
                name='uq_asignacion_tutor_activo', nulls_distinct=False,
            ),
            models.UniqueConstraint(
                fields=['calendario_academico', 'curso', 'materia_curso', 'profesor'],
                condition=Q(tipo='MATERIA', estado='ACTIVO', eliminado_at__isnull=True),
                name='uq_asignacion_materia_activa', nulls_distinct=False,
            ),
        ]
        indexes = [
            models.Index(
                fields=['calendario_academico', 'curso', 'estado'],
                name='ix_asignacion_gestion_curso',
            ),
            models.Index(
                fields=['profesor', 'calendario_academico', 'estado'],
                name='ix_asignacion_prof_gestion',
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.tipo == self.Tipo.MATERIA and not self.materia_curso_id:
            errors['materia_curso'] = 'La materia del curso es obligatoria para este tipo.'
        if self.tipo == self.Tipo.TUTOR_CURSO and self.materia_curso_id:
            errors['materia_curso'] = 'La tutoría de curso no admite una materia.'
        if self.fecha_fin and self.fecha_inicio and self.fecha_fin < self.fecha_inicio:
            errors['fecha_fin'] = 'No puede ser anterior a la fecha de inicio.'

        unidad_curso_id = None
        if self.curso_id:
            unidad_curso_id = self.curso.paralelo.grado.unidad_educativa_id
            if self.curso.paralelo.grado.unidad_educativa.estado != 'ACTIVO':
                errors['curso'] = 'La unidad educativa del curso está inactiva.'
        if self.profesor_id:
            if not self.profesor.estado:
                errors['profesor'] = 'El profesor está inactivo.'
            if unidad_curso_id and self.profesor.unidad_id != unidad_curso_id:
                errors['profesor'] = 'El profesor pertenece a otra unidad educativa.'
        if self.materia_curso_id and self.materia_curso.curso_id != self.curso_id:
            errors['materia_curso'] = 'La materia debe corresponder al curso.'
        if self.calendario_academico_id:
            calendario = self.calendario_academico
            if unidad_curso_id and calendario.unidad_educativa_id != unidad_curso_id:
                errors['calendario_academico'] = 'La gestión pertenece a otra unidad educativa.'
            if self.fecha_inicio and self.fecha_inicio < calendario.fecha_inicio:
                errors['fecha_inicio'] = 'Debe estar dentro de la gestión académica.'
            if self.fecha_inicio and self.fecha_inicio > calendario.fecha_fin:
                errors['fecha_inicio'] = 'Debe estar dentro de la gestión académica.'
            if self.fecha_fin and self.fecha_fin > calendario.fecha_fin:
                errors['fecha_fin'] = 'Debe estar dentro de la gestión académica.'
        if errors:
            raise ValidationError(errors)


class BloqueHorario(models.Model):
    unidad_educativa = models.ForeignKey(
        UnidadEducativa, on_delete=models.PROTECT, related_name='bloques_horarios',
    )
    turno = models.CharField(max_length=10, choices=UnidadEducativa.TURNOS)
    dia = models.PositiveSmallIntegerField()
    orden = models.PositiveSmallIntegerField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    tipo = models.CharField(max_length=20, default='CLASE')
    estado = models.CharField(max_length=20, default='ACTIVO')

    class Meta:
        db_table = 'horarios_bloque'
        constraints = [
            models.CheckConstraint(condition=Q(dia__gte=1, dia__lte=7), name='ck_bloque_dia'),
            models.CheckConstraint(condition=Q(orden__gt=0), name='ck_bloque_orden'),
            models.CheckConstraint(condition=Q(hora_inicio__lt=F('hora_fin')), name='ck_bloque_horas'),
            models.UniqueConstraint(
                fields=['unidad_educativa', 'turno', 'dia', 'orden'], name='uq_bloque_unidad_turno_dia',
            ),
        ]


class HorarioClase(models.Model):
    asignacion_docente = models.ForeignKey(
        AsignacionDocente, on_delete=models.PROTECT, related_name='horarios',
    )
    profesor = models.ForeignKey(
        'personal.Profesor', on_delete=models.PROTECT, related_name='horarios_clase',
    )
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name='horarios_clase')
    aula = models.ForeignKey(Aula, on_delete=models.PROTECT, related_name='horarios_clase')
    bloque_horario = models.ForeignKey(
        BloqueHorario, on_delete=models.PROTECT, related_name='horarios_clase',
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, default='ACTIVO')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'horarios_clase'
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=F('fecha_inicio')),
                name='ck_horario_clase_fechas',
            ),
            models.UniqueConstraint(
                fields=['asignacion_docente', 'bloque_horario', 'fecha_inicio'],
                name='uq_horario_asignacion_bloque',
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.asignacion_docente_id:
            if self.profesor_id != self.asignacion_docente.profesor_id:
                errors['profesor'] = 'Debe coincidir con la asignación docente.'
            if self.curso_id != self.asignacion_docente.curso_id:
                errors['curso'] = 'Debe coincidir con la asignación docente.'
        if self.curso_id and self.bloque_horario_id:
            unidad_id = self.curso.paralelo.grado.unidad_educativa_id
            if self.bloque_horario.unidad_educativa_id != unidad_id:
                errors['bloque_horario'] = 'Debe pertenecer a la unidad educativa del curso.'
            if self.aula_id and self.aula.modulo_id and self.aula.modulo.colegio_fk_id:
                if self.aula.modulo.colegio_fk_id != self.curso.paralelo.grado.unidad_educativa.colegio_id:
                    errors['aula'] = 'Debe pertenecer al colegio de la unidad educativa.'
        if errors:
            raise ValidationError(errors)


class ConfiguracionEvaluacion(models.Model):
    class ReglaRedondeo(models.TextChoices):
        NORMAL = 'NORMAL', 'Normal'
        TRUNCAR = 'TRUNCAR', 'Truncar'
        SUPERIOR = 'SUPERIOR', 'Superior'

    calendario_academico = models.ForeignKey(
        'calendario.CalendarioAcademico', on_delete=models.PROTECT,
        related_name='configuraciones_evaluacion',
    )
    nivel = models.CharField(max_length=50)
    nota_minima = models.DecimalField(max_digits=7, decimal_places=2)
    nota_maxima = models.DecimalField(max_digits=7, decimal_places=2)
    nota_aprobacion = models.DecimalField(max_digits=7, decimal_places=2)
    decimales = models.PositiveSmallIntegerField(default=2)
    regla_redondeo = models.CharField(max_length=20, choices=ReglaRedondeo.choices)
    estado = models.CharField(max_length=20, default='ACTIVO')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'evaluacion_configuracion'
        constraints = [
            models.UniqueConstraint(fields=['calendario_academico', 'nivel'], name='uq_eval_config_calendario_nivel'),
            models.CheckConstraint(condition=Q(nota_minima__lt=F('nota_maxima')), name='ck_eval_config_rango'),
            models.CheckConstraint(condition=Q(nota_aprobacion__gte=F('nota_minima'), nota_aprobacion__lte=F('nota_maxima')), name='ck_eval_config_aprobacion'),
            models.CheckConstraint(condition=Q(decimales__gte=0, decimales__lte=4), name='ck_eval_config_decimales'),
        ]


class DimensionEvaluacion(models.Model):
    configuracion = models.ForeignKey(ConfiguracionEvaluacion, on_delete=models.PROTECT, related_name='dimensiones')
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=100)
    ponderacion = models.DecimalField(max_digits=7, decimal_places=2)
    orden = models.PositiveSmallIntegerField()
    estado = models.CharField(max_length=20, default='ACTIVO')

    class Meta:
        db_table = 'evaluacion_dimension'
        constraints = [
            models.UniqueConstraint(fields=['configuracion', 'codigo'], name='uq_eval_dimension_codigo'),
            models.CheckConstraint(condition=Q(ponderacion__gt=0, ponderacion__lte=100), name='ck_eval_dimension_ponderacion'),
            models.CheckConstraint(condition=Q(orden__gt=0), name='ck_eval_dimension_orden'),
        ]


class ActividadEvaluacion(models.Model):
    asignacion_docente = models.ForeignKey(AsignacionDocente, on_delete=models.PROTECT, related_name='actividades_evaluacion')
    periodo = models.ForeignKey('calendario.Periodo', on_delete=models.PROTECT, related_name='actividades_evaluacion')
    dimension = models.ForeignKey(DimensionEvaluacion, on_delete=models.PROTECT, related_name='actividades')
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    fecha = models.DateField()
    puntaje_maximo = models.DecimalField(max_digits=7, decimal_places=2)
    ponderacion = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=20, default='ACTIVO')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='actividades_evaluacion_creadas', null=True, blank=True)
    created_by_snapshot = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'evaluacion_actividad'
        constraints = [
            models.CheckConstraint(condition=Q(puntaje_maximo__gt=0), name='ck_eval_actividad_puntaje'),
            models.CheckConstraint(condition=Q(ponderacion__isnull=True) | Q(ponderacion__gt=0, ponderacion__lte=100), name='ck_eval_actividad_ponderacion'),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.periodo_id and self.dimension_id and self.periodo.calendario_id != self.dimension.configuracion.calendario_academico_id:
            errors['dimension'] = 'La dimensión no corresponde al calendario del periodo.'
        if self.periodo_id and self.asignacion_docente_id:
            unidad = self.asignacion_docente.curso.paralelo.grado.unidad_educativa_id
            if self.periodo.calendario.unidad_educativa_id != unidad:
                errors['asignacion_docente'] = 'La asignación no corresponde al contexto del periodo.'
        if errors:
            raise ValidationError(errors)


class Calificacion(models.Model):
    actividad = models.ForeignKey(ActividadEvaluacion, on_delete=models.PROTECT, related_name='calificaciones')
    historial_inscripcion = models.ForeignKey('estudiantes.HistorialInscripcion', on_delete=models.PROTECT, related_name='calificaciones')
    valor = models.DecimalField(max_digits=7, decimal_places=2)
    estado = models.CharField(max_length=20, default='REGISTRADA')
    registrada_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'evaluacion_calificacion'
        constraints = [
            models.UniqueConstraint(fields=['actividad', 'historial_inscripcion'], name='uq_eval_calificacion_actividad'),
            models.CheckConstraint(condition=Q(valor__gte=0), name='ck_eval_calificacion_valor'),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.actividad_id and self.valor is not None and self.valor > self.actividad.puntaje_maximo:
            errors['valor'] = 'No puede superar el puntaje máximo de la actividad.'
        if self.actividad_id and self.historial_inscripcion_id:
            if self.historial_inscripcion.curso_nuevo_id != self.actividad.asignacion_docente.curso_id:
                errors['historial_inscripcion'] = 'No corresponde al curso de la actividad.'
        if errors:
            raise ValidationError(errors)


class CorreccionCalificacion(models.Model):
    class Estado(models.TextChoices):
        SOLICITADA = 'SOLICITADA', 'Solicitada'
        APROBADA = 'APROBADA', 'Aprobada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    calificacion = models.ForeignKey(Calificacion, on_delete=models.PROTECT, related_name='correcciones')
    valor_anterior = models.DecimalField(max_digits=7, decimal_places=2)
    valor_nuevo = models.DecimalField(max_digits=7, decimal_places=2)
    motivo = models.TextField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.SOLICITADA)
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='correcciones_solicitadas', null=True, blank=True)
    solicitante_snapshot = models.CharField(max_length=200, null=True, blank=True)
    autorizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='correcciones_autorizadas', null=True, blank=True)
    autorizador_snapshot = models.CharField(max_length=200, null=True, blank=True)
    solicitado_at = models.DateTimeField(auto_now_add=True)
    resuelto_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'evaluacion_correccion'
        constraints = [
            models.CheckConstraint(condition=~Q(valor_anterior=F('valor_nuevo')), name='ck_eval_correccion_cambio'),
            models.CheckConstraint(condition=Q(valor_anterior__gte=0, valor_nuevo__gte=0), name='ck_eval_correccion_valores'),
            models.UniqueConstraint(fields=['calificacion'], condition=Q(estado='SOLICITADA'), name='uq_eval_correccion_solicitada'),
            models.CheckConstraint(condition=Q(estado='SOLICITADA', resuelto_at__isnull=True) | Q(estado__in=['APROBADA', 'RECHAZADA'], resuelto_at__isnull=False), name='ck_eval_correccion_resolucion'),
            models.CheckConstraint(condition=~Q(estado='APROBADA') | Q(autorizado_por__isnull=False) | Q(autorizador_snapshot__isnull=False), name='ck_eval_correccion_autoriza'),
        ]


class ResultadoTrimestral(models.Model):
    historial_inscripcion = models.ForeignKey('estudiantes.HistorialInscripcion', on_delete=models.PROTECT, related_name='resultados_trimestrales')
    materia = models.ForeignKey(Materia, on_delete=models.PROTECT, related_name='resultados_trimestrales')
    periodo = models.ForeignKey('calendario.Periodo', on_delete=models.PROTECT, related_name='resultados_trimestrales')
    resultado = models.DecimalField(max_digits=7, decimal_places=2)
    condicion = models.CharField(max_length=20)
    calculado_at = models.DateTimeField()
    estado = models.CharField(max_length=20, default='CALCULADO')

    class Meta:
        db_table = 'evaluacion_resultado_trimestral'
        constraints = [
            models.UniqueConstraint(fields=['historial_inscripcion', 'materia', 'periodo'], name='uq_eval_resultado_trimestral'),
            models.CheckConstraint(condition=Q(resultado__gte=0), name='ck_eval_resultado_tri_valor'),
        ]

    def clean(self):
        super().clean()
        if self.historial_inscripcion_id and self.periodo_id:
            if self.historial_inscripcion.unidad_id != self.periodo.calendario.unidad_educativa_id:
                raise ValidationError('La inscripción y el periodo no pertenecen al mismo contexto.')
        if self.historial_inscripcion_id and self.materia_id:
            if not MateriaCurso.objects.filter(curso_id=self.historial_inscripcion.curso_nuevo_id, materia_id=self.materia_id).exists():
                raise ValidationError({'materia': 'La materia no corresponde al curso de la inscripción.'})


class ResultadoAnual(models.Model):
    historial_inscripcion = models.ForeignKey('estudiantes.HistorialInscripcion', on_delete=models.PROTECT, related_name='resultados_anuales')
    materia = models.ForeignKey(Materia, on_delete=models.PROTECT, related_name='resultados_anuales')
    resultado = models.DecimalField(max_digits=7, decimal_places=2)
    condicion = models.CharField(max_length=20)
    calculado_at = models.DateTimeField()
    estado = models.CharField(max_length=20, default='CALCULADO')

    class Meta:
        db_table = 'evaluacion_resultado_anual'
        constraints = [
            models.UniqueConstraint(fields=['historial_inscripcion', 'materia'], name='uq_eval_resultado_anual'),
            models.CheckConstraint(condition=Q(resultado__gte=0), name='ck_eval_resultado_anual_valor'),
        ]

    def clean(self):
        super().clean()
        if self.historial_inscripcion_id and self.materia_id:
            if not MateriaCurso.objects.filter(curso_id=self.historial_inscripcion.curso_nuevo_id, materia_id=self.materia_id).exists():
                raise ValidationError({'materia': 'La materia no corresponde al curso de la inscripción.'})

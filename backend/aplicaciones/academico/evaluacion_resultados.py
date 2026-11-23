from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import ActividadEvaluacion, Calificacion, ResultadoTrimestral, ResultadoAnual
from .evaluacion_calculo import NotaEntrada, DimensionEntrada, calcular_trimestre, calcular_anual


def recalcular_resultados(calificacion):
    """Caller must hold its enrollment row lock inside transaction.atomic()."""
    if not connection.in_atomic_block:
        raise RuntimeError('El recálculo requiere una transacción y bloqueo de inscripción.')
    activity = calificacion.actividad
    period = activity.periodo
    config = activity.dimension.configuracion
    history = calificacion.historial_inscripcion
    subject_id = activity.asignacion_docente.materia_curso.materia_id
    if config.calendario_academico_id != period.calendario_id or config.nivel != history.curso_nuevo.paralelo.grado.nivel_educativo:
        raise ValidationError('La configuración no corresponde al periodo y nivel del estudiante.')
    activities = list(ActividadEvaluacion.objects.filter(
        periodo=period, asignacion_docente__curso_id=history.curso_nuevo_id,
        asignacion_docente__materia_curso__materia_id=subject_id, estado='ACTIVO',
    ).select_related('dimension'))
    dimensions = list(config.dimensiones.filter(estado='ACTIVO').order_by('orden', 'pk'))
    dim_ids = {d.pk for d in dimensions}
    if any(a.dimension.configuracion_id != config.pk or a.dimension_id not in dim_ids for a in activities):
        raise ValidationError('Hay actividades con dimensiones/configuraciones incompatibles.')
    grades = {g.actividad_id: g for g in Calificacion.objects.filter(historial_inscripcion=history, actividad__in=activities, estado='REGISTRADA')}
    if len(grades) != len(activities):
        raise ValidationError('Faltan calificaciones válidas; no se puede aprobar la corrección.')
    inputs = [DimensionEntrada(d.ponderacion, tuple(NotaEntrada(grades[a.pk].valor, a.puntaje_maximo, a.ponderacion) for a in activities if a.dimension_id == d.pk)) for d in dimensions]
    value = calcular_trimestre(inputs, minimo=config.nota_minima, maximo=config.nota_maxima, decimales=config.decimales, redondeo=config.regla_redondeo)
    def condition(result):
        return 'APROBADO' if result >= config.nota_aprobacion else 'REPROBADO'
    result, _ = ResultadoTrimestral.objects.update_or_create(historial_inscripcion=history, materia_id=subject_id, periodo=period, defaults={'resultado': value, 'condicion': condition(value), 'calculado_at': timezone.now()})
    periods = set(period.calendario.periodos.exclude(estado='CAN').values_list('pk', flat=True))
    results = list(ResultadoTrimestral.objects.filter(historial_inscripcion=history, materia_id=subject_id, periodo_id__in=periods).order_by('periodo_id'))
    annual = ResultadoAnual.objects.filter(historial_inscripcion=history, materia_id=subject_id).first()
    if {r.periodo_id for r in results} != periods:
        if annual:
            raise ValidationError('El resultado anual existente está incompleto. Corrija sus periodos antes de aprobar.')
        return result, None
    annual_value = calcular_anual(tuple(r.resultado for r in results), decimales=config.decimales, redondeo=config.regla_redondeo)
    annual, _ = ResultadoAnual.objects.update_or_create(historial_inscripcion=history, materia_id=subject_id, defaults={'resultado': annual_value, 'condicion': condition(annual_value), 'calculado_at': timezone.now()})
    return result, annual

"""Agregaciones institucionales; nunca devuelve datos individuales."""
import math
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from aplicaciones.academico.models import Curso, MateriaCurso, ResultadoTrimestral
from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from aplicaciones.estudiantes.models import Estudiante, AsistenciaEstudiante, IncidenteDisciplinario
from aplicaciones.institucion.models import UnidadEducativa


class ErrorSerieAnalitica(Exception):
    """Datos agregados no representables en una serie opcional."""


def calcular_serie(qs, campo, etiqueta):
    filas = []
    for item in qs[:100]:
        try:
            valor = float(item[etiqueta])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ErrorSerieAnalitica from exc
        if not math.isfinite(valor):
            raise ErrorSerieAnalitica
        filas.append({'etiqueta': str(item[campo]) if item[campo] is not None else 'Sin curso', 'valor': round(valor, 2)})
    return filas


def contexto(alcance, params):
    permitidos = {'colegio', 'unidad_educativa', 'calendario_academico', 'periodo', 'curso', 'materia'}
    if set(params) - permitidos:
        raise ValidationError('Filtro no permitido.')
    campo = serializers.IntegerField(min_value=1)
    valores = {k: campo.run_validation(v) for k, v in params.items() if v not in ('', None)}
    if valores.get('colegio', alcance['colegio_id']) != alcance['colegio_id']:
        raise ValidationError('Contexto institucional no disponible.')
    unidad_id = valores.get('unidad_educativa', alcance['unidad_id'])
    if not unidad_id or (alcance['tipo'] == 'UNIDAD' and unidad_id != alcance['unidad_id']):
        raise ValidationError('Contexto institucional no disponible.')
    unidad = get_object_or_404(UnidadEducativa.objects.select_related('colegio'), pk=unidad_id, colegio_id=alcance['colegio_id'])
    calendario = get_object_or_404(CalendarioAcademico, pk=valores.get('calendario_academico'), unidad_educativa=unidad)
    periodo = get_object_or_404(Periodo, pk=valores['periodo'], calendario=calendario) if valores.get('periodo') else None
    curso = get_object_or_404(Curso, pk=valores['curso'], paralelo__grado__unidad_educativa=unidad) if valores.get('curso') else None
    materia = valores.get('materia')
    if materia:
        if not curso:
            raise ValidationError({'materia': 'Seleccione primero un curso.'})
        get_object_or_404(MateriaCurso, curso=curso, materia_id=materia, materia__unidad_educativa=unidad)
    return unidad, calendario, periodo, curso, materia


def resumen(alcance, params):
    unidad, calendario, periodo, curso, materia = contexto(alcance, params)
    actuales = Estudiante.objects.filter(unidad=unidad, estado=True).filter(Q(curso__isnull=True) | Q(curso__paralelo__grado__unidad_educativa=unidad))
    resultados = ResultadoTrimestral.objects.filter(historial_inscripcion__unidad=unidad, periodo__calendario=calendario,
        historial_inscripcion__curso_nuevo__paralelo__grado__unidad_educativa=unidad)
    asistencias = AsistenciaEstudiante.objects.filter(historial_inscripcion__unidad=unidad,
        sesion_clase__asignacion_docente__calendario_academico=calendario,
        sesion_clase__asignacion_docente__curso_id=F('historial_inscripcion__curso_nuevo_id'))
    inicio, fin = (periodo.fecha_inicio, periodo.fecha_fin) if periodo else (calendario.fecha_inicio, calendario.fecha_fin)
    asistencias = asistencias.filter(sesion_clase__fecha__range=(inicio, fin))
    incidentes = IncidenteDisciplinario.objects.filter(historial_inscripcion__unidad=unidad,
        historial_inscripcion__curso_nuevo__paralelo__grado__unidad_educativa=unidad, fecha__date__range=(inicio, fin))
    if periodo:
        resultados = resultados.filter(periodo=periodo)
    if curso:
        actuales = actuales.filter(curso=curso)
        resultados = resultados.filter(historial_inscripcion__curso_nuevo=curso)
        asistencias = asistencias.filter(historial_inscripcion__curso_nuevo=curso)
        incidentes = incidentes.filter(historial_inscripcion__curso_nuevo=curso)
    if materia:
        resultados = resultados.filter(materia_id=materia)
        asistencias = asistencias.filter(sesion_clase__asignacion_docente__materia_curso__materia_id=materia)
    conteos = {x['estado_asistencia']: x['total'] for x in asistencias.order_by().values('estado_asistencia').annotate(total=Count('pk'))}
    total = sum(conteos.values())
    condiciones = {x['condicion']: x['total'] for x in resultados.order_by().values('condicion').annotate(total=Count('pk'))}
    aprobados, reprobados = condiciones.get('APROBADO', 0), condiciones.get('REPROBADO', 0)
    evaluados = aprobados + reprobados
    promedio = resultados.aggregate(valor=Avg('resultado'))['valor']
    errores_parciales = []
    def serie(nombre, qs, campo, etiqueta):
        try:
            return calcular_serie(qs, campo, etiqueta)
        except ErrorSerieAnalitica:
            errores_parciales.append({'componente': nombre, 'mensaje': 'No fue posible calcular esta serie.'})
            return None
    return {
        'contexto': {'colegio': unidad.colegio_id, 'unidad_educativa': unidad.pk, 'calendario_academico': calendario.pk,
                     'periodo': periodo.pk if periodo else None, 'curso': curso.pk if curso else None, 'materia': materia},
        'indicadores': {'matricula_actual': actuales.count(), 'promedio_general': round(float(promedio), 2) if promedio is not None else None,
                        'porcentaje_aprobacion': round(100 * aprobados / evaluados, 2) if evaluados else None,
                        'porcentaje_asistencia': round(100 * conteos.get('PRESENTE', 0) / total, 2) if total else None,
                        'asistencia_total': total, 'incidentes_total': incidentes.count()},
        'series': {
            'matricula_por_curso': serie('matricula_por_curso', actuales.order_by().values('curso__nombre').annotate(total=Count('pk')).order_by('curso__nombre'), 'curso__nombre', 'total'),
            'rendimiento_por_materia': serie('rendimiento_por_materia', resultados.order_by().values('materia__nombre').annotate(promedio=Avg('resultado')).order_by('materia__nombre'), 'materia__nombre', 'promedio'),
            'rendimiento_por_periodo': serie('rendimiento_por_periodo', resultados.order_by().values('periodo__nombre').annotate(promedio=Avg('resultado')).order_by('periodo__nombre'), 'periodo__nombre', 'promedio'),
            'asistencia_por_estado': [{'etiqueta': k, 'valor': v} for k, v in sorted(conteos.items())],
            'asistencia_por_fecha': serie('asistencia_por_fecha', asistencias.order_by().values('sesion_clase__fecha').annotate(total=Count('pk')).order_by('sesion_clase__fecha'), 'sesion_clase__fecha', 'total'),
            'incidentes_por_fecha': serie('incidentes_por_fecha', incidentes.order_by().annotate(dia=TruncDate('fecha')).values('dia').annotate(total=Count('pk')).order_by('dia'), 'dia', 'total'),
        },
        'metadatos': {'generado_en': timezone.now().isoformat(), 'errores_parciales': errores_parciales,
            'matricula_actual': {'tipo_temporal': 'ACTUAL', 'filtros_aplicados': ['colegio', 'unidad_educativa', 'curso'],
                'filtros_no_aplicables': ['calendario_academico', 'periodo', 'materia'],
                'advertencia': 'Fotografía de estudiantes activos en este momento. No representa la matrícula histórica de la gestión o periodo seleccionado.'},
            'rendimiento': {'filtros_aplicados': ['colegio', 'unidad_educativa', 'calendario_academico', 'periodo', 'curso', 'materia'], 'filtros_no_aplicables': []},
            'asistencia': {'filtros_aplicados': ['colegio', 'unidad_educativa', 'calendario_academico', 'periodo', 'curso', 'materia'], 'filtros_no_aplicables': [], 'advertencia': 'Porcentaje de registros con estado PRESENTE sobre el total.'},
            'incidentes': {'filtros_aplicados': ['colegio', 'unidad_educativa', 'calendario_academico', 'periodo', 'curso'], 'filtros_no_aplicables': ['materia'], 'advertencia': 'La gestión y el periodo se aplican por fecha del incidente.'},
            'metricas_omitidas': ['Riesgo académico: contexto histórico ambiguo.', 'Incidentes por tipo: categoría de texto libre no garantiza ausencia de datos personales.']},
    }

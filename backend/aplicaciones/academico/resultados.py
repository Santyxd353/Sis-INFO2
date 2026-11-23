"""HU-17: cálculo de promedios trimestrales y anuales (Ley N.º 070).

Reglas oficiales:
- Cada dimensión aporta (nota obtenida / puntaje posible de sus actividades)
  * ponderación de la dimensión.
- El promedio trimestral es la suma de los aportes de las 5 dimensiones.
- El redondeo a entero (según la regla configurada) se aplica SOLO al total
  trimestral, nunca a las dimensiones por separado.
- El promedio anual es el promedio simple de los promedios trimestrales ya
  calculados (no se exige que existan los 3; se promedian los que haya).
"""
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP, Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import (
    ActividadEvaluacion, Calificacion, ConfiguracionEvaluacion,
    ResultadoAnual, ResultadoTrimestral,
)


def configuracion_vigente(curso, periodo):
    nivel = curso.paralelo.grado.nivel_educativo
    return ConfiguracionEvaluacion.objects.filter(
        calendario_academico=periodo.calendario, nivel=nivel,
    ).prefetch_related('dimensiones').first()


def _redondear(valor, configuracion):
    cuantizador = Decimal('1').scaleb(-configuracion.decimales)
    if configuracion.regla_redondeo == ConfiguracionEvaluacion.ReglaRedondeo.TRUNCAR:
        return valor.quantize(cuantizador, rounding=ROUND_DOWN)
    if configuracion.regla_redondeo == ConfiguracionEvaluacion.ReglaRedondeo.SUPERIOR:
        return valor.quantize(cuantizador, rounding=ROUND_CEILING)
    return valor.quantize(cuantizador, rounding=ROUND_HALF_UP)


def desglose_por_dimension(historial_inscripcion, materia, periodo, configuracion=None):
    """Aporte de cada dimensión al promedio de una materia/periodo.

    Devuelve una lista de dicts {dimension, obtenido, puntaje_posible, aporte}
    en el orden oficial de las dimensiones. Es la base tanto del cálculo del
    promedio trimestral (HU-17) como del detalle que se imprime en el
    boletín (HU-19).
    """
    curso = historial_inscripcion.curso_nuevo
    configuracion = configuracion or configuracion_vigente(curso, periodo)
    if configuracion is None:
        raise ValueError(
            'No existe una configuración de evaluación para el nivel y la '
            'gestión académica de este curso (HU-15).',
        )

    actividades = list(ActividadEvaluacion.objects.filter(
        periodo=periodo,
        asignacion_docente__curso=curso,
        asignacion_docente__materia_curso__materia=materia,
    ).select_related('dimension'))

    desglose = []
    for dimension in configuracion.dimensiones.order_by('orden'):
        de_la_dimension = [a for a in actividades if a.dimension_id == dimension.pk]
        puntaje_posible = sum((a.puntaje_maximo for a in de_la_dimension), Decimal('0'))
        obtenido = Decimal('0')
        aporte = Decimal('0')
        if puntaje_posible > 0:
            obtenido = Calificacion.objects.filter(
                actividad__in=de_la_dimension, historial_inscripcion=historial_inscripcion,
            ).aggregate(total=Sum('valor'))['total'] or Decimal('0')
            aporte = (obtenido / puntaje_posible) * dimension.ponderacion
        desglose.append({
            'dimension': dimension, 'obtenido': obtenido,
            'puntaje_posible': puntaje_posible, 'aporte': aporte,
        })
    return desglose, configuracion


def calcular_resultado_trimestral(historial_inscripcion, materia, periodo):
    desglose, configuracion = desglose_por_dimension(historial_inscripcion, materia, periodo)
    total = sum((item['aporte'] for item in desglose), Decimal('0'))
    resultado = _redondear(total, configuracion)
    condicion = 'APROBADO' if resultado >= configuracion.nota_aprobacion else 'REPROBADO'
    registro, _ = ResultadoTrimestral.objects.update_or_create(
        historial_inscripcion=historial_inscripcion, materia=materia, periodo=periodo,
        defaults={'resultado': resultado, 'condicion': condicion, 'calculado_at': timezone.now()},
    )
    calcular_resultado_anual(historial_inscripcion, materia)
    return registro


def calcular_resultado_anual(historial_inscripcion, materia):
    trimestrales = list(ResultadoTrimestral.objects.filter(
        historial_inscripcion=historial_inscripcion, materia=materia,
    ).select_related('periodo__calendario'))
    if not trimestrales:
        return None

    curso = historial_inscripcion.curso_nuevo
    configuracion = configuracion_vigente(curso, trimestrales[0].periodo)
    promedio = sum((r.resultado for r in trimestrales), Decimal('0')) / Decimal(len(trimestrales))
    resultado = _redondear(promedio, configuracion) if configuracion else promedio
    nota_aprobacion = configuracion.nota_aprobacion if configuracion else Decimal('51')
    condicion = 'APROBADO' if resultado >= nota_aprobacion else 'REPROBADO'

    registro, _ = ResultadoAnual.objects.update_or_create(
        historial_inscripcion=historial_inscripcion, materia=materia,
        defaults={'resultado': resultado, 'condicion': condicion, 'calculado_at': timezone.now()},
    )
    return registro


def recalcular_por_calificacion(calificacion):
    actividad = calificacion.actividad
    materia = actividad.asignacion_docente.materia_curso.materia
    return calcular_resultado_trimestral(
        calificacion.historial_inscripcion, materia, actividad.periodo,
    )


def historial_actual(estudiante):
    """Resuelve el registro de HistorialInscripcion que representa la
    matrícula vigente del estudiante en su curso actual."""
    if estudiante.curso_id is None:
        return None
    return estudiante.historial_inscripciones.filter(
        curso_nuevo_id=estudiante.curso_id,
    ).order_by('-fecha_inscripcion').first()

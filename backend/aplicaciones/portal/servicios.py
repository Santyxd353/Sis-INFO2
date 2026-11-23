"""Read-only portal projections. No recalculation, events, or private file URLs."""
from django.db.models import Count, F, Q, Exists, OuterRef
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from aplicaciones.academico.models import MateriaCurso, ResultadoTrimestral, ResultadoAnual, HorarioClase
from aplicaciones.asistencia.models import DetalleAsistencia
from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from aplicaciones.comunicacion.models import Aviso, DestinatarioComunicado
from aplicaciones.estudiantes.models import HistorialInscripcion, AsistenciaEstudiante, DocumentoAcademicoEmitido
from aplicaciones.usuarios.feature_access import full_name
from aplicaciones.estudiantes.alcance_familiar import coherent_students


def positive(params, key):
    if key not in params:
        return None
    value = params[key]
    if not value or not value.isascii() or not value.isdecimal() or int(value) <= 0:
        raise ValidationError({key: 'Debe ser un entero positivo.'})
    return int(value)


def calendar_context(unit_id, calendar_id, period_id):
    calendars = CalendarioAcademico.objects.filter(unidad_educativa_id=unit_id).order_by('-activo', '-año', '-pk')
    calendar = get_object_or_404(calendars, pk=calendar_id) if calendar_id else calendars.first()
    periods = Periodo.objects.filter(calendario=calendar).order_by('fecha_inicio', 'pk') if calendar else Periodo.objects.none()
    period = get_object_or_404(periods, pk=period_id) if period_id else None
    return ([{'id': c.pk, 'anio': c.año, 'activo': c.activo} for c in calendars],
            {'id': calendar.pk, 'anio': calendar.año, 'activo': calendar.activo} if calendar else None,
            list(periods.values('id', 'nombre', 'estado')), calendar, period)


def student_row(student, enrollment=None):
    course = enrollment.curso_nuevo if enrollment else student.curso
    return {'id': student.pk, 'nombre': full_name(student.usuario), 'curso': course.nombre if course else None,
            'unidad_educativa': student.unidad_id, 'unidad_nombre': student.unidad.nombre}


def enrollment_for(student, calendar):
    if calendar is None:
        return None
    enrollments = HistorialInscripcion.objects.filter(estudiante=student, unidad_id=student.unidad_id,
        curso_nuevo__paralelo__grado__unidad_educativa_id=student.unidad_id).exclude(
            tipo_movimiento__in=['RETIRADO', 'TRANSLADADO']).select_related('curso_nuevo')
    # Enrollment has no calendar FK: prefer explicit calendar-bearing evidence.
    evidence = Q(resultados_trimestrales__periodo__calendario=calendar) | Q(
        asistencias__sesion_clase__asignacion_docente__calendario_academico=calendar) | Q(
        documentos_academicos__calendario_academico=calendar)
    found = enrollments.filter(evidence).order_by('-fecha_inscripcion', '-pk').first()
    if found:
        return found
    return enrollments.filter(curso_nuevo_id=student.curso_id,
        fecha_inscripcion__date__lte=calendar.fecha_fin).order_by('-fecha_inscripcion', '-pk').first()


def notes(enrollment, calendar, period):
    if enrollment is None or calendar is None:
        return []
    subjects = MateriaCurso.objects.filter(curso_id=enrollment.curso_nuevo_id).filter(
        Q(materia__unidad_educativa__isnull=True) | Q(materia__unidad_educativa_id=enrollment.unidad_id)).values('materia_id')
    results = ResultadoTrimestral.objects.filter(historial_inscripcion=enrollment, periodo__calendario=calendar,
        materia_id__in=subjects, estado='CALCULADO').select_related('materia', 'periodo').order_by('materia__nombre', 'periodo__fecha_inicio')
    if period:
        results = results.filter(periodo=period)
    grouped = {}
    for result in results:
        row = grouped.setdefault(result.materia_id, {'materia': result.materia.nombre, 'periodos': [], 'anual': None})
        row['periodos'].append({'id': result.periodo_id, 'nombre': result.periodo.nombre,
            'nota': str(result.resultado), 'condicion': result.condicion})
    # Annual results have no calendar FK. Omit ambiguous cross-year totals.
    if not period:
        ambiguous = ResultadoTrimestral.objects.filter(historial_inscripcion=enrollment).exclude(
            periodo__calendario=calendar).values_list('materia_id', flat=True)
        for result in ResultadoAnual.objects.filter(historial_inscripcion=enrollment,
                materia_id__in=grouped, estado='CALCULADO').exclude(materia_id__in=ambiguous):
            grouped[result.materia_id]['anual'] = {'nota': str(result.resultado), 'condicion': result.condicion}
    return list(grouped.values())


def attendance_queries(unit_ids, calendar, period, enrollment=None, student=None):
    sessions = AsistenciaEstudiante.objects.filter(
        historial_inscripcion__unidad_id__in=unit_ids,
        historial_inscripcion__curso_nuevo__paralelo__grado__unidad_educativa_id=F('historial_inscripcion__unidad_id'),
        historial_inscripcion__estudiante__unidad_id=F('historial_inscripcion__unidad_id'),
        historial_inscripcion__estudiante__usuario__unidad_id=F('historial_inscripcion__unidad_id'),
        sesion_clase__asignacion_docente__curso_id=F('historial_inscripcion__curso_nuevo_id'),
        sesion_clase__asignacion_docente__materia_curso__curso_id=F('historial_inscripcion__curso_nuevo_id'),
        sesion_clase__asignacion_docente__profesor__unidad_id=F('historial_inscripcion__unidad_id'),
        sesion_clase__asignacion_docente__profesor__usuario__unidad_id=F('historial_inscripcion__unidad_id'),
        sesion_clase__asignacion_docente__calendario_academico=calendar,
        sesion_clase__asignacion_docente__calendario_academico__unidad_educativa_id=F('historial_inscripcion__unidad_id'),
        sesion_clase__fecha__range=(calendar.fecha_inicio, calendar.fecha_fin),
    ).exclude(sesion_clase__estado__in=['CANCELADA', 'CANCELADO']).filter(
        Q(sesion_clase__asignacion_docente__materia_curso__materia__unidad_educativa__isnull=True)
        | Q(sesion_clase__asignacion_docente__materia_curso__materia__unidad_educativa_id=F('historial_inscripcion__unidad_id')))
    legacy = DetalleAsistencia.objects.filter(estudiante__unidad_id__in=unit_ids,
        estudiante__usuario__unidad_id=F('estudiante__unidad_id'),
        registro__asignacion__curso__paralelo__grado__unidad_educativa_id=F('estudiante__unidad_id'),
        registro__fecha__range=(calendar.fecha_inicio, calendar.fecha_fin)).filter(
            Q(registro__periodo__calendario=calendar) | Q(registro__periodo__isnull=True)).filter(
                Q(registro__asignacion__materia__unidad_educativa__isnull=True)
                | Q(registro__asignacion__materia__unidad_educativa_id=F('estudiante__unidad_id')))
    if period:
        sessions = sessions.filter(sesion_clase__fecha__range=(period.fecha_inicio, period.fecha_fin))
        legacy = legacy.filter(registro__fecha__range=(period.fecha_inicio, period.fecha_fin)).filter(
            Q(registro__periodo=period) | Q(registro__periodo__isnull=True))
    if enrollment:
        sessions = sessions.filter(historial_inscripcion=enrollment)
        legacy = legacy.filter(registro__asignacion__curso_id=enrollment.curso_nuevo_id)
    if student:
        sessions = sessions.filter(historial_inscripcion__estudiante=student)
        legacy = legacy.filter(estudiante=student)
    return sessions, legacy


def attendance(enrollment=None, calendar=None, period=None, student=None):
    empty = {'fuente': 'SIN_DATOS', 'total': 0, 'presentes': 0, 'faltas': 0,
             'atrasos': 0, 'licencias': 0, 'porcentaje': None, 'registros': []}
    if not enrollment or not calendar:
        return empty
    sessions, legacy = attendance_queries([student.unidad_id], calendar, period, enrollment, student)
    use_sessions = sessions.exists()
    qs = sessions if use_sessions else legacy
    state_field = 'estado_asistencia' if use_sessions else 'estado'
    counts = {row[state_field]: row['total'] for row in qs.values(state_field).annotate(total=Count('pk')).order_by()}
    total = sum(counts.values())
    if not total:
        return empty
    normalized = {'P': 'PRESENTE', 'A': 'AUSENTE', 'T': 'ATRASO', 'L': 'LICENCIA'}
    counts = {normalized.get(state, state): count for state, count in counts.items()}
    rows = []
    if use_sessions:
        for row in sessions.select_related('sesion_clase__asignacion_docente__materia_curso__materia').order_by('-sesion_clase__fecha', '-pk')[:50]:
            mc = row.sesion_clase.asignacion_docente.materia_curso
            rows.append({'id': row.pk, 'fecha': row.sesion_clase.fecha.isoformat(), 'estado': row.estado_asistencia,
                         'materia': mc.materia.nombre if mc else ''})
    else:
        for row in legacy.select_related('registro__asignacion__materia').order_by('-registro__fecha', '-pk')[:50]:
            rows.append({'id': row.pk, 'fecha': row.registro.fecha.isoformat(), 'estado': normalized[row.estado],
                         'materia': row.registro.asignacion.materia.nombre})
    return {'fuente': 'SESIONES' if use_sessions else 'LEGACY', 'total': total,
        'presentes': counts.get('PRESENTE', 0), 'faltas': counts.get('AUSENTE', 0), 'atrasos': counts.get('ATRASO', 0),
        'licencias': counts.get('LICENCIA', 0), 'porcentaje': round(100 * counts.get('PRESENTE', 0) / total, 2), 'registros': rows}


def schedules(enrollment, calendar):
    if not enrollment or not calendar:
        return []
    today = timezone.localdate()
    qs = HorarioClase.objects.filter(curso_id=enrollment.curso_nuevo_id,
        asignacion_docente__curso_id=F('curso_id'), profesor_id=F('asignacion_docente__profesor_id'),
        asignacion_docente__materia_curso__curso_id=F('curso_id'),
        asignacion_docente__calendario_academico=calendar, asignacion_docente__estado='ACTIVO',
        profesor__unidad_id=calendar.unidad_educativa_id, profesor__usuario__unidad_id=calendar.unidad_educativa_id,
        asignacion_docente__eliminado_at__isnull=True, estado='ACTIVO', bloque_horario__estado='ACTIVO',
        bloque_horario__unidad_educativa_id=calendar.unidad_educativa_id,
        fecha_inicio__lte=today, asignacion_docente__fecha_inicio__lte=today).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=today)).filter(
        Q(asignacion_docente__fecha_fin__isnull=True) | Q(asignacion_docente__fecha_fin__gte=today))
    qs = qs.filter(Q(asignacion_docente__materia_curso__materia__unidad_educativa__isnull=True)
        | Q(asignacion_docente__materia_curso__materia__unidad_educativa_id=calendar.unidad_educativa_id))
    school_id = calendar.unidad_educativa.colegio_id
    qs = qs.filter(aula__estado=True, aula__eliminado_at__isnull=True,
        aula__modulo__estado='ACTIVO', aula__modulo__eliminado_at__isnull=True).filter(
            Q(aula__modulo__unidad_educativa__colegio_id=school_id) | Q(aula__modulo__unidad_educativa__isnull=True)
        ).filter(Q(aula__modulo__colegio_fk_id=school_id) | Q(aula__modulo__colegio_fk__isnull=True)).filter(
            Q(aula__modulo__unidad_educativa__colegio_id=school_id) | Q(aula__modulo__colegio_fk_id=school_id))
    if not calendar.fecha_inicio <= today <= calendar.fecha_fin:
        return []
    return [{'id': row.pk, 'dia': row.bloque_horario.dia,
        'hora_inicio': row.bloque_horario.hora_inicio.isoformat(), 'hora_fin': row.bloque_horario.hora_fin.isoformat(),
        'materia': row.asignacion_docente.materia_curso.materia.nombre, 'docente': full_name(row.profesor.usuario),
        'aula': row.aula.nombre} for row in qs.select_related('bloque_horario', 'profesor__usuario',
            'asignacion_docente__materia_curso__materia', 'aula').order_by('bloque_horario__dia', 'bloque_horario__hora_inicio')]


def documents(enrollment, calendar, period):
    if not enrollment or not calendar:
        return []
    qs = DocumentoAcademicoEmitido.objects.filter(tipo='BOLETIN', historial_inscripcion=enrollment,
        calendario_academico=calendar).filter(Q(periodo__isnull=True) | Q(periodo__calendario=calendar))
    if period:
        qs = qs.filter(periodo=period)
    return [{'id': row.pk, 'tipo': row.tipo, 'periodo': row.periodo.nombre if row.periodo else None,
        'version': row.version, 'created_at': row.emitido_at.isoformat(),
        'descarga_url': f'/api/estudiantes/documentos-academicos/{row.pk}/descargar/'}
        for row in qs.select_related('periodo').order_by('-emitido_at', '-pk')[:10]]


def communications(user):
    messages = DestinatarioComunicado.objects.filter(usuario=user, comunicado__unidad_educativa_id=user.unidad_id,
        comunicado__estado__in=['PUBLICADO', 'ARCHIVADO']).select_related('comunicado').order_by('-comunicado__publicado_at', '-pk')[:10]
    inbox = Aviso.objects.filter(usuario=user, unidad_educativa_id=user.unidad_id)
    return ([{'id': row.comunicado_id, 'titulo': row.comunicado.titulo, 'prioridad': row.comunicado.prioridad,
              'leido_at': row.leido_at, 'publicado_at': row.comunicado.publicado_at} for row in messages],
            {'no_leidas': inbox.filter(leida_at__isnull=True).count(), 'recientes': list(inbox.values(
                'id', 'tipo', 'titulo', 'created_at', 'leida_at', 'comunicado')[:10])})


def valid_results(unit_ids, calendar, period):
    subjects = MateriaCurso.objects.filter(curso_id=OuterRef('historial_inscripcion__curso_nuevo_id'), materia_id=OuterRef('materia_id')).filter(
        Q(materia__unidad_educativa__isnull=True) | Q(materia__unidad_educativa_id=OuterRef('historial_inscripcion__unidad_id')))
    qs = ResultadoTrimestral.objects.filter(estado='CALCULADO', periodo__calendario=calendar,
        historial_inscripcion__unidad_id__in=unit_ids,
        historial_inscripcion__unidad_id=F('periodo__calendario__unidad_educativa_id'),
        historial_inscripcion__curso_nuevo__paralelo__grado__unidad_educativa_id=F('historial_inscripcion__unidad_id'),
        historial_inscripcion__estudiante__unidad_id=F('historial_inscripcion__unidad_id'),
        historial_inscripcion__estudiante__usuario__unidad_id=F('historial_inscripcion__unidad_id'),
    ).filter(Exists(subjects))
    return qs.filter(periodo=period) if period else qs

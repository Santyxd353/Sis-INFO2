from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from aplicaciones.estudiantes.models import HistorialInscripcion
from aplicaciones.usuarios.auditoria import registrar_evento
from aplicaciones.usuarios.feature_access import full_name
from aplicaciones.usuarios.tenancy import validar_unidad
from .models import Calificacion, CorreccionCalificacion
from .evaluacion_resultados import recalcular_resultados


class CorrectionConflict(APIException):
    status_code = 409
    default_detail = 'La solicitud ya se resolvió o la calificación cambió. Actualice la lista.'


def validate_grade(grade, value):
    activity = grade.actividad
    enrollment = grade.historial_inscripcion
    config = activity.dimension.configuracion
    if activity.periodo.estado != 'FIN':
        raise ValidationError('Solo se corrigen calificaciones de periodos finalizados.')
    if activity.estado != 'ACTIVO' or grade.estado != 'REGISTRADA':
        raise ValidationError('La actividad o calificación no está vigente.')
    assignment = activity.asignacion_docente
    if not assignment.materia_curso_id or assignment.curso_id != enrollment.curso_nuevo_id:
        raise ValidationError('La calificación no corresponde al curso inscrito.')
    if assignment.materia_curso.curso_id != assignment.curso_id or assignment.curso.paralelo.grado.unidad_educativa_id != enrollment.unidad_id or activity.periodo.calendario.unidad_educativa_id != enrollment.unidad_id:
        raise ValidationError('Contexto académico inconsistente.')
    if assignment.calendario_academico_id and assignment.calendario_academico_id != activity.periodo.calendario_id:
        raise ValidationError('La asignación no corresponde al calendario.')
    if config.calendario_academico_id != activity.periodo.calendario_id or config.nivel != enrollment.curso_nuevo.paralelo.grado.nivel_educativo:
        raise ValidationError('Configuración incompatible con el periodo/nivel.')
    if value < 0 or value > activity.puntaje_maximo or value == grade.valor:
        raise ValidationError({'valor_nuevo': 'Debe ser diferente y estar dentro del puntaje de la actividad.'})


def audit(request, correction, action, previous):
    registrar_evento(accion=action, entidad='CORRECCION_CALIFICACION', entidad_id=correction.pk, request=request, unidad=correction.calificacion.historial_inscripcion.unidad, cambios={'estado_anterior': previous, 'estado_nuevo': correction.estado})


@transaction.atomic
def solicitar_correccion(*, request, calificacion_id, valor_nuevo, motivo):
    # One stable parent lock also serializes result creation when no result exists yet.
    history_id = Calificacion.objects.values_list('historial_inscripcion_id', flat=True).get(pk=calificacion_id)
    HistorialInscripcion.objects.select_for_update().get(pk=history_id)
    grade = Calificacion.objects.select_for_update().get(pk=calificacion_id)
    validar_unidad(request.user, grade.historial_inscripcion.unidad)
    if not hasattr(request.user, 'profesor') or grade.actividad.asignacion_docente.profesor_id != request.user.profesor.pk:
        raise PermissionDenied('Solo el docente de la actividad puede solicitar la corrección.')
    validate_grade(grade, valor_nuevo)
    if CorreccionCalificacion.objects.filter(calificacion=grade, estado='SOLICITADA').exists():
        raise CorrectionConflict('Ya existe una solicitud pendiente para esta nota.')
    if not motivo.strip():
        raise ValidationError({'motivo': 'El motivo es obligatorio.'})
    row = CorreccionCalificacion.objects.create(calificacion=grade, valor_anterior=grade.valor, valor_nuevo=valor_nuevo, motivo=motivo.strip(), solicitado_por=request.user, solicitante_snapshot=full_name(request.user))
    audit(request, row, 'CREAR', None)
    return row


@transaction.atomic
def resolver_correccion(*, request, correccion_id, aprobar):
    original = CorreccionCalificacion.objects.select_related('calificacion').get(pk=correccion_id)
    HistorialInscripcion.objects.select_for_update().get(pk=original.calificacion.historial_inscripcion_id)
    grade = Calificacion.objects.select_for_update().get(pk=original.calificacion_id)
    row = CorreccionCalificacion.objects.select_for_update().get(pk=correccion_id)
    row.calificacion = grade
    validar_unidad(request.user, grade.historial_inscripcion.unidad)
    if row.solicitado_por_id == request.user.pk:
        raise PermissionDenied('No puede resolver su propia solicitud.')
    if row.estado != 'SOLICITADA':
        raise CorrectionConflict()
    if aprobar:
        if grade.valor != row.valor_anterior:
            raise CorrectionConflict()
        validate_grade(grade, row.valor_nuevo)
        grade.valor = row.valor_nuevo
        grade.save(update_fields=['valor', 'updated_at'])
        recalcular_resultados(grade)
    row.estado = 'APROBADA' if aprobar else 'RECHAZADA'
    row.autorizado_por = request.user
    row.autorizador_snapshot = full_name(request.user)
    row.resuelto_at = timezone.now()
    row.save(update_fields=['estado', 'autorizado_por', 'autorizador_snapshot', 'resuelto_at'])
    audit(request, row, 'ACTUALIZAR', 'SOLICITADA')
    return row

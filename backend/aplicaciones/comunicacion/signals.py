from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from aplicaciones.academico.models import ConfiguracionEvaluacion, ResultadoTrimestral
from aplicaciones.asistencia.models import DetalleAsistencia
from aplicaciones.estudiantes.models import AccionDisciplinaria, AsistenciaEstudiante, DocumentoAcademicoEmitido
from aplicaciones.usuarios.models import Accion, ModeloPermitido, PermisoPuesto, Puesto
from aplicaciones.usuarios.tenancy import normalizar_nombre
from .servicios import emitir_alerta_estudiante


@receiver(post_save, sender=Puesto)
def permisos_director(sender, instance, created, raw=False, **kwargs):
    if created and not raw and normalizar_nombre(instance.nombre) == 'director':
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='comunicacion')
        accion, _ = Accion.objects.get_or_create(nombre='gestionar')
        PermisoPuesto.objects.get_or_create(puesto=instance, modelo=modelo, accion=accion)


@receiver(post_save, sender=DetalleAsistencia)
def asistencia_heredada(sender, instance, raw=False, **kwargs):
    if raw or instance.estado not in ('A', 'T'):
        return
    course = instance.registro.asignacion.curso
    if instance.estudiante.curso_id != course.pk:
        return
    tipo = 'FALTA' if instance.estado == 'A' else 'ATRASO'
    emitir_alerta_estudiante(estudiante=instance.estudiante, unidad=course.paralelo.grado.unidad_educativa,
        tipo=tipo, titulo='Registro de asistencia', cuerpo='Se registró una ausencia.' if tipo == 'FALTA' else 'Se registró un atraso.',
        clave_evento=f'asistencia-detalle:{instance.pk}:{tipo}', datos={'detalle_asistencia': instance.pk})


@receiver(post_save, sender=AsistenciaEstudiante)
def asistencia_sesion(sender, instance, raw=False, **kwargs):
    if raw or instance.estado_asistencia not in ('AUSENTE', 'ATRASO') or instance.justificada:
        return
    enrollment = instance.historial_inscripcion
    assignment = instance.sesion_clase.asignacion_docente
    course = assignment.curso
    unit = course.paralelo.grado.unidad_educativa
    if (enrollment.curso_nuevo_id != course.pk or enrollment.unidad_id != unit.pk
            or assignment.calendario_academico.unidad_educativa_id != unit.pk):
        return
    tipo = 'FALTA' if instance.estado_asistencia == 'AUSENTE' else 'ATRASO'
    emitir_alerta_estudiante(estudiante=enrollment.estudiante, unidad=unit, tipo=tipo,
        titulo='Registro de asistencia', cuerpo='Se registró una ausencia.' if tipo == 'FALTA' else 'Se registró un atraso.',
        clave_evento=f'asistencia-sesion:{instance.pk}:{tipo}', datos={'asistencia': instance.pk})


@receiver(post_save, sender=ResultadoTrimestral)
def nota_baja(sender, instance, raw=False, **kwargs):
    if raw or instance.estado != 'CALCULADO':
        return
    enrollment = instance.historial_inscripcion
    unit = instance.periodo.calendario.unidad_educativa
    course = enrollment.curso_nuevo
    if enrollment.unidad_id != unit.pk or course.paralelo.grado.unidad_educativa_id != unit.pk:
        return
    if not course.materias.filter(materia_id=instance.materia_id).exists():
        return
    config = ConfiguracionEvaluacion.objects.filter(calendario_academico=instance.periodo.calendario,
        nivel=course.paralelo.grado.nivel_educativo, estado='ACTIVO').first()
    threshold = config.nota_aprobacion if config else Decimal('51')
    # Django acepta cadenas decimales en save() sin reemplazar el valor de
    # la instancia por Decimal antes de emitir post_save.
    if Decimal(str(instance.resultado)) < threshold:
        emitir_alerta_estudiante(estudiante=enrollment.estudiante, unidad=unit, tipo='NOTA_BAJA',
            titulo='Resultado académico', cuerpo='Hay un resultado académico que requiere atención.',
            clave_evento=f'resultado-trimestral:{instance.pk}:NOTA_BAJA', datos={'resultado_trimestral': instance.pk})


@receiver(post_save, sender=AccionDisciplinaria)
def citacion(sender, instance, raw=False, **kwargs):
    if raw or instance.tipo != 'CITACION' or instance.estado != 'PENDIENTE':
        return
    enrollment = instance.incidente.historial_inscripcion
    if instance.tutor_estudiante_id and instance.tutor_estudiante.estudiante_id != enrollment.estudiante_id:
        return
    emitir_alerta_estudiante(estudiante=enrollment.estudiante, unidad=enrollment.unidad, tipo='CITACION',
        titulo='Citación escolar', cuerpo='Tiene una citación escolar pendiente. Consulte el detalle con la institución.',
        clave_evento=f'citacion:{instance.pk}', datos={'citacion': instance.pk})


@receiver(post_save, sender=DocumentoAcademicoEmitido)
def boletin(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.tipo != 'BOLETIN' or not instance.historial_inscripcion_id:
        return
    enrollment = instance.historial_inscripcion
    unit = instance.calendario_academico.unidad_educativa
    if enrollment.unidad_id != unit.pk or (instance.periodo_id and instance.periodo.calendario_id != instance.calendario_academico_id):
        return
    emitir_alerta_estudiante(estudiante=enrollment.estudiante, unidad=unit, tipo='BOLETIN',
        titulo='Boletín disponible', cuerpo='Su boletín académico está disponible en la aplicación.',
        clave_evento=f'boletin:{instance.pk}', datos={'documento_academico': instance.pk})

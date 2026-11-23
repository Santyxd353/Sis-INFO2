import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from aplicaciones.usuarios.auditoria import registrar_evento
from .models import Aviso, Comunicado, DestinatarioComunicado, PreferenciaNotificacion, TipoAviso, preferencias_predeterminadas
from .seguridad import audiencia_curso, exigir_gestor, usuarios_unidad

logger = logging.getLogger(__name__)


def preferencias(usuario):
    guardadas = PreferenciaNotificacion.objects.filter(usuario=usuario).values_list('categorias', flat=True).first() or {}
    return {**preferencias_predeterminadas(), **guardadas}


def _push(aviso_id):
    """El callback captura sólo ID y vuelve a comprobar afiliación/preferencia."""
    try:
        from aplicaciones.usuarios.notificaciones import enviar_notificacion
        aviso = Aviso.objects.select_related('usuario').get(pk=aviso_id)
        if (not usuarios_unidad(aviso.unidad_educativa_id).filter(pk=aviso.usuario_id).exists()
                or not preferencias(aviso.usuario).get(aviso.tipo, True)):
            return
        enviar_notificacion([aviso.usuario_id], 'Nueva notificación escolar',
                            'Ingresa a la aplicación para consultar el detalle.',
                            {'notificacion_id': aviso.pk, 'comunicado_id': aviso.comunicado_id, 'tipo': aviso.tipo})
    except Exception:
        # Un proveedor externo nunca revierte el evento durable ya confirmado.
        logger.exception('No fue posible enviar el aviso %s.', aviso_id)


def crear_avisos(*, unidad, usuarios, tipo, titulo, cuerpo, clave_evento, comunicado=None, datos=None):
    if tipo not in TipoAviso.values:
        raise ValidationError({'tipo': 'Categoría desconocida.'})
    creadas = 0
    with transaction.atomic():
        for usuario_id in sorted(set(usuarios_unidad(unidad.pk).filter(pk__in=usuarios).values_list('pk', flat=True))):
            aviso, created = Aviso.objects.get_or_create(
                unidad_educativa=unidad, usuario_id=usuario_id, clave_evento=clave_evento,
                defaults={'tipo': tipo, 'titulo': titulo, 'cuerpo': cuerpo, 'comunicado': comunicado, 'datos': datos or {}},
            )
            if created:
                creadas += 1
                transaction.on_commit(lambda pk=aviso.pk: _push(pk))
    return creadas


@transaction.atomic
def emitir_alerta_estudiante(*, estudiante, tipo, titulo, cuerpo, clave_evento, unidad=None, datos=None):
    """Integración administrativa: llamador confiable aporta clave estable, sin crear cobros.

    APIs deben autorizar al actor antes de invocar. Las señales aportan unidad de
    la fuente y este servicio exige coherencia entre perfil, curso y unidad.
    """
    from aplicaciones.estudiantes.models import TutorEstudiante
    unidad = unidad or estudiante.unidad
    if not unidad or estudiante.unidad_id != unidad.pk or not estudiante.estado:
        return 0
    if (estudiante.usuario.unidad_id != unidad.pk
            or not estudiante.curso_id
            or estudiante.curso.paralelo.grado.unidad_educativa_id != unidad.pk):
        return 0
    ids = [estudiante.usuario_id, *TutorEstudiante.objects.filter(estudiante=estudiante).values_list('tutor_id', flat=True)]
    return crear_avisos(unidad=unidad, usuarios=ids, tipo=tipo, titulo=titulo, cuerpo=cuerpo,
                       clave_evento=clave_evento, datos={'estudiante': estudiante.pk, **(datos or {})})


@transaction.atomic
def publicar(comunicado_id, usuario, request=None):
    comunicado = Comunicado.objects.select_for_update().select_related('unidad_educativa').get(pk=comunicado_id)
    exigir_gestor(usuario, comunicado.unidad_educativa)
    if comunicado.estado == Comunicado.Estado.ARCHIVADO:
        raise ValidationError('Un comunicado archivado no se puede publicar.')
    if comunicado.estado == Comunicado.Estado.PUBLICADO:
        return comunicado
    if comunicado.curso_id:
        if comunicado.curso.paralelo.grado.unidad_educativa_id != comunicado.unidad_educativa_id:
            raise ValidationError({'curso': 'El curso no pertenece a la unidad educativa.'})
        audiencia = audiencia_curso(comunicado.unidad_educativa_id, comunicado.curso_id)
    else:
        audiencia = usuarios_unidad(comunicado.unidad_educativa_id)
    ids = list(audiencia.values_list('pk', flat=True).distinct())
    DestinatarioComunicado.objects.bulk_create([DestinatarioComunicado(comunicado=comunicado, usuario_id=pk) for pk in ids])
    comunicado.estado = Comunicado.Estado.PUBLICADO
    comunicado.publicado_at = timezone.now()
    comunicado.save(update_fields=['estado', 'publicado_at'])
    crear_avisos(unidad=comunicado.unidad_educativa, usuarios=ids, tipo=TipoAviso.COMUNICADO,
                 titulo=comunicado.titulo, cuerpo=comunicado.cuerpo,
                 clave_evento=f'comunicado:{comunicado.pk}', comunicado=comunicado)
    registrar_evento(accion='ACTUALIZAR', entidad='COMUNICADO', usuario=usuario, request=request,
                     unidad=comunicado.unidad_educativa, entidad_id=comunicado.pk,
                     cambios={'estado_anterior': 'BORRADOR', 'estado_nuevo': 'PUBLICADO'})
    return comunicado

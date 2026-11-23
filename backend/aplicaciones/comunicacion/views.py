from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.usuarios.auditoria import registrar_evento
from aplicaciones.usuarios.tenancy import unidades_permitidas
from .models import Aviso, Comunicado, DestinatarioComunicado, PreferenciaNotificacion, TipoAviso
from .seguridad import exigir_gestor, puede_gestionar, usuarios_unidad
from .serializers import AlertaSerializer, AvisoSerializer, ComunicadoSerializer
from .servicios import emitir_alerta_estudiante, preferencias, publicar


class ComunicacionPagination(PageNumberPagination):
    page_size = 20


def receptor_actual(user):
    return bool(user.unidad_id and usuarios_unidad(user.unidad_id).filter(pk=user.pk).exists())


class ComunicadoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                        mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = ComunicadoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ComunicacionPagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs = Comunicado.objects.select_related('unidad_educativa', 'curso__paralelo__grado')
        if puede_gestionar(user):
            qs = qs.filter(unidad_educativa_id__in=unidades_permitidas(user))
        elif receptor_actual(user):
            qs = qs.filter(unidad_educativa_id=user.unidad_id, destinatarios__usuario=user,
                           estado__in=['PUBLICADO', 'ARCHIVADO'])
        else:
            qs = qs.none()
        for key in ('unidad_educativa', 'curso'):
            value = self.request.query_params.get(key)
            if value:
                try:
                    value = int(value)
                    if value <= 0:
                        raise ValueError
                except ValueError:
                    raise ValidationError({key: 'Debe ser un entero positivo.'})
                qs = qs.filter(**{f'{key}_id': value})
        state = self.request.query_params.get('estado')
        if state:
            if state not in Comunicado.Estado.values:
                raise ValidationError({'estado': 'Estado desconocido.'})
            qs = qs.filter(estado=state)
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save(creado_por=self.request.user)
        registrar_evento(accion='CREAR', entidad='COMUNICADO', request=self.request,
                         unidad=obj.unidad_educativa, entidad_id=obj.pk, cambios=['titulo', 'cuerpo', 'curso'])

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        obj = Comunicado.objects.select_for_update().get(pk=obj.pk)
        exigir_gestor(request.user, obj.unidad_educativa)
        if obj.estado != Comunicado.Estado.BORRADOR:
            raise ValidationError('Sólo se pueden editar borradores.')
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        registrar_evento(accion='ACTUALIZAR', entidad='COMUNICADO', request=request,
                         unidad=obj.unidad_educativa, entidad_id=obj.pk, cambios=list(serializer.validated_data))
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def publicar(self, request, pk=None):
        obj = self.get_object()
        obj = publicar(obj.pk, request.user, request)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def archivar(self, request, pk=None):
        obj = self.get_object()
        obj = Comunicado.objects.select_for_update().select_related('unidad_educativa').get(pk=obj.pk)
        exigir_gestor(request.user, obj.unidad_educativa)
        if obj.estado == Comunicado.Estado.BORRADOR:
            raise ValidationError('Publique el comunicado antes de archivarlo.')
        if obj.estado != Comunicado.Estado.ARCHIVADO:
            obj.estado = Comunicado.Estado.ARCHIVADO
            obj.save(update_fields=['estado'])
            registrar_evento(accion='ARCHIVAR', entidad='COMUNICADO', request=request,
                             unidad=obj.unidad_educativa, entidad_id=obj.pk,
                             cambios={'estado_anterior': 'PUBLICADO', 'estado_nuevo': 'ARCHIVADO'})
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def leer(self, request, pk=None):
        obj = self.get_object()
        if (obj.estado == Comunicado.Estado.BORRADOR
                or request.user.unidad_id != obj.unidad_educativa_id
                or not receptor_actual(request.user)):
            raise PermissionDenied('No es destinatario del comunicado.')
        receipt = get_object_or_404(DestinatarioComunicado.objects.select_for_update(), comunicado=obj, usuario=request.user)
        if receipt.leido_at is None:
            receipt.leido_at = timezone.now()
            receipt.save(update_fields=['leido_at'])
            Aviso.objects.filter(usuario=request.user, comunicado=obj, leida_at__isnull=True).update(leida_at=receipt.leido_at)
            registrar_evento(accion='ACTUALIZAR', entidad='LECTURA_COMUNICADO', request=request,
                             unidad=obj.unidad_educativa, entidad_id=receipt.pk, cambios=['leido_at'])
        return Response(self.get_serializer(obj).data)


class AvisoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AvisoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ComunicacionPagination

    def get_queryset(self):
        user = self.request.user
        qs = Aviso.objects.filter(usuario=user, unidad_educativa_id=user.unidad_id) if receptor_actual(user) else Aviso.objects.none()
        unread = self.request.query_params.get('no_leidas')
        if unread is not None:
            if unread.lower() not in ('true', 'false'):
                raise ValidationError({'no_leidas': 'Use true o false.'})
            if unread.lower() == 'true':
                qs = qs.filter(leida_at__isnull=True)
        category = self.request.query_params.get('tipo')
        if category:
            if category not in TipoAviso.values:
                raise ValidationError({'tipo': 'Categoría desconocida.'})
            qs = qs.filter(tipo=category)
        return qs

    @action(detail=False, methods=['get'])
    def resumen(self, request):
        return Response({'no_leidas': self.get_queryset().filter(leida_at__isnull=True).count()})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def leer(self, request, pk=None):
        obj = self.get_object()
        Aviso.objects.filter(pk=obj.pk, leida_at__isnull=True).update(leida_at=timezone.now())
        obj.refresh_from_db()
        return Response(self.get_serializer(obj).data)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def preferencias_api(request):
    if request.method == 'PATCH':
        if not isinstance(request.data, dict) or any(key not in TipoAviso.values or type(value) is not bool for key, value in request.data.items()):
            raise ValidationError('Sólo se admiten categorías conocidas con valores booleanos.')
        with transaction.atomic():
            preference, _ = PreferenciaNotificacion.objects.get_or_create(usuario=request.user)
            preference = PreferenciaNotificacion.objects.select_for_update().get(pk=preference.pk)
            preference.categorias = {**preference.categorias, **request.data}
            preference.save(update_fields=['categorias'])
    return Response(preferencias(request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def alertas_api(request):
    if not puede_gestionar(request.user):
        raise PermissionDenied('Se requiere un director con permiso de comunicación institucional.')
    serializer = AlertaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    student = get_object_or_404(Estudiante.objects.select_related('unidad', 'usuario', 'curso__paralelo__grado'), pk=values['estudiante'])
    exigir_gestor(request.user, student.unidad)
    created = emitir_alerta_estudiante(estudiante=student, tipo=values['tipo'], titulo=values['titulo'],
        cuerpo=values['cuerpo'], clave_evento=f"manual:{values['tipo']}:{student.pk}:{values['clave_evento']}")
    if created:
        registrar_evento(accion='CREAR', entidad='ALERTA_COMUNICACION', request=request,
                         unidad=student.unidad, entidad_id=student.pk, cambios={'resultado': values['tipo'], 'cantidad_filas': created})
    return Response({'creadas': created}, status=201)

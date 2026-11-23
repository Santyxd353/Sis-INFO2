from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication

from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.usuarios.feature_access import SchoolPagination, id_filters, scoped

from . import pasarela, qr
from .models import Pago, SolicitudQR
from .serializers import (
    CrearSolicitudQRSerializer, ResolverSolicitudQRSerializer, RevocarBecaSerializer, SolicitudQRSerializer,
)
from .views import BaseConsultaFinanzas, PermisoFinanzas, _auditar, _filtrar_opcion, en_alcance


def solicitudes_base():
    return SolicitudQR.objects.select_related(
        'estudiante__usuario', 'estudiante__curso', 'pago', 'solicitado_por', 'unidad_educativa',
    ).prefetch_related('obligaciones__cuota')


class SolicitudQRViewSet(ReadOnlyModelViewSet):
    """HU-25: la familia o la caja generan un QR y el pago se registra al confirmarse."""

    serializer_class = SolicitudQRSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoFinanzas]
    pagination_class = SchoolPagination
    modelo_permiso = 'pago-qr'
    acciones_personalizadas = {
        'create': 'crear', 'verificar': 'listar', 'anular': 'crear',
        'resolver': 'conciliar', 'simular_cobro': 'conciliar',
    }
    lectura_familiar = True
    acciones_familiares = ('create', 'verificar', 'anular')

    def get_queryset(self):
        queryset = en_alcance(self.request.user, solicitudes_base(), 'unidad_educativa_id')
        params = self.request.query_params
        queryset = id_filters(queryset, params, {
            'estudiante': 'estudiante_id', 'unidad_educativa': 'unidad_educativa_id',
        })
        queryset = _filtrar_opcion(queryset, params, 'estado', 'estado', SolicitudQR.Estado.values)
        for parametro, campo in (('desde', 'created_at__date__gte'), ('hasta', 'created_at__date__lte')):
            valor = params.get(parametro)
            if valor:
                queryset = queryset.filter(**{campo: serializers.DateField().run_validation(valor)})
        return queryset.order_by('-created_at')

    def _respuesta(self, solicitud_id, codigo=status.HTTP_200_OK):
        return Response(self.get_serializer(solicitudes_base().get(pk=solicitud_id)).data, status=codigo)

    def create(self, request):
        datos = CrearSolicitudQRSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        estudiante = get_object_or_404(
            en_alcance(request.user, Estudiante.objects.all(), 'unidad_id', None),
            pk=datos.validated_data['estudiante'],
        )
        solicitud, creada = qr.crear_solicitud(request.user, estudiante, datos.validated_data.get('obligaciones'))
        if creada:
            _auditar(request, 'CREAR', 'SOLICITUD_QR', solicitud, solicitud.unidad_educativa, metodo='QR')
        return self._respuesta(solicitud.pk, status.HTTP_201_CREATED if creada else status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def verificar(self, request, pk=None):
        anterior = self.get_object()
        solicitud = qr.verificar(anterior.pk)
        if solicitud.estado != anterior.estado:
            _auditar(request, 'ACTUALIZAR', 'SOLICITUD_QR', solicitud, solicitud.unidad_educativa,
                     estado_anterior=anterior.estado, estado_nuevo=solicitud.estado)
        return self._respuesta(solicitud.pk)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        datos = RevocarBecaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        solicitud = qr.anular(self.get_object().pk, request.user, datos.validated_data['motivo'])
        _auditar(request, 'DESACTIVAR', 'SOLICITUD_QR', solicitud, solicitud.unidad_educativa,
                 estado_anterior='PENDIENTE', estado_nuevo='ANULADA')
        return self._respuesta(solicitud.pk)

    @action(detail=True, methods=['post'])
    def resolver(self, request, pk=None):
        datos = ResolverSolicitudQRSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        solicitud = qr.resolver(
            self.get_object().pk, request.user, datos.validated_data['accion'], datos.validated_data['motivo'],
        )
        _auditar(request, 'ACTUALIZAR', 'SOLICITUD_QR', solicitud, solicitud.unidad_educativa,
                 estado_anterior='OBSERVADA', estado_nuevo=solicitud.estado, resultado=datos.validated_data['accion'])
        return self._respuesta(solicitud.pk)

    @action(detail=True, methods=['post'], url_path='simular-cobro')
    def simular_cobro(self, request, pk=None):
        """Solo en modo simulado: hace que la pasarela de prueba informe el cobro."""
        solicitud = self.get_object()
        if not (pasarela.es_qr_simulado(solicitud.qr_id) and pasarela.simulada(solicitud.unidad_educativa.colegio_id)):
            raise PermissionDenied('Solo puedes simular el cobro de un QR de demostración habilitado.')
        monto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0).run_validation(
            request.data.get('monto', solicitud.monto),
        )
        pasarela.marcar_cobro_simulado(solicitud.qr_id, monto, timezone.now())
        return self._respuesta(qr.verificar(solicitud.pk, tardia=True).pk)


class ConciliacionQRView(BaseConsultaFinanzas):
    """HU-25: cuadre entre lo cobrado por la pasarela y lo registrado en el sistema."""

    modelo_permiso = 'pago-qr'
    acciones_personalizadas = {None: 'conciliar'}

    def get(self, request):
        filtros = {'unidad_educativa': 'unidad_educativa_id'}
        solicitudes = id_filters(scoped(solicitudes_base(), request.user, 'unidad_educativa_id'), request.query_params, filtros)
        pagos = id_filters(
            scoped(Pago.objects.filter(metodo=Pago.Metodo.QR), request.user, 'unidad_educativa_id'),
            request.query_params, filtros,
        )
        for parametro, campo_solicitud, campo_pago in (
            ('desde', 'created_at__date__gte', 'fecha_pago__gte'), ('hasta', 'created_at__date__lte', 'fecha_pago__lte'),
        ):
            valor = request.query_params.get(parametro)
            if valor:
                fecha = serializers.DateField().run_validation(valor)
                solicitudes, pagos = solicitudes.filter(**{campo_solicitud: fecha}), pagos.filter(**{campo_pago: fecha})
        por_resolver = solicitudes.filter(estado__in=(SolicitudQR.Estado.OBSERVADA, SolicitudQR.Estado.PAGADA)).exclude(
            estado=SolicitudQR.Estado.PAGADA, pago__estado=Pago.Estado.VALIDO,
        )
        return Response({
            'modo_simulado': pasarela.simulada() or solicitudes.filter(
                unidad_educativa__colegio_id__in=settings.FINANZAS_QR_DEMO_COLEGIO_IDS,
            ).exists(),
            'resumen': qr.resumen_conciliacion(solicitudes, pagos),
            'por_resolver': SolicitudQRSerializer(por_resolver[:100], many=True, context={'request': request}).data,
        })


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def qr_simulado(request, qr_id):
    """Imagen del QR de prueba; no existe fuera del modo simulado."""
    if not pasarela.es_qr_simulado(qr_id):
        raise Http404
    solicitud = get_object_or_404(SolicitudQR.objects.select_related('unidad_educativa'), qr_id=qr_id)
    if not pasarela.simulada(solicitud.unidad_educativa.colegio_id):
        raise Http404
    return HttpResponse(pasarela.imagen_qr_simulado(qr_id), content_type='image/png',
                        headers={'Cache-Control': 'no-store'})

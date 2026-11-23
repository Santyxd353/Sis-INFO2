"""HU-28: alertas de pago (recordatorios y bandeja de avisos de la familia)."""
from django.utils import timezone
from rest_framework import mixins, serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication

from aplicaciones.usuarios.auditoria import registrar_evento
from aplicaciones.usuarios.feature_access import SchoolPagination, id_filters, scoped
from aplicaciones.usuarios.models import Notificacion

from .avisos import TIPOS_AVISO, enviar_recordatorios_pago
from .models import ObligacionPago, RecordatorioPago
from .views import BaseConsultaFinanzas


class RecordatoriosPagoSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=RecordatorioPago.Tipo.choices)
    dias = serializers.IntegerField(min_value=1, max_value=30, default=5)
    unidad_educativa = serializers.IntegerField(min_value=1, required=False)
    curso = serializers.IntegerField(min_value=1, required=False)


class RecordatorioPagoSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.SerializerMethodField()
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = RecordatorioPago
        fields = ('id', 'estudiante', 'estudiante_nombre', 'tipo', 'tipo_display', 'fecha', 'monto', 'created_at')

    def get_estudiante_nombre(self, obj):
        return f'{obj.estudiante.usuario.nombre} {obj.estudiante.usuario.apellido}'.strip()


class AvisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ('id', 'tipo', 'titulo', 'mensaje', 'leida', 'fecha')
        read_only_fields = fields


class RecordatoriosPagoView(BaseConsultaFinanzas):
    """GET: últimos recordatorios enviados. POST: envía recordatorios de cuotas vencidas o por vencer."""

    # Permisos: GET = listar, POST = crear (enviar recordatorios).
    modelo_permiso = 'alerta-pago'

    def get(self, request):
        queryset = scoped(
            RecordatorioPago.objects.select_related('estudiante__usuario'), request.user, 'estudiante__unidad_id',
        )
        queryset = id_filters(queryset, request.query_params, {
            'unidad_educativa': 'estudiante__unidad_id', 'curso': 'estudiante__curso_id',
        })
        return Response(RecordatorioPagoSerializer(queryset[:50], many=True).data)

    def post(self, request):
        datos = RecordatoriosPagoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        valores = datos.validated_data
        obligaciones = scoped(ObligacionPago.objects.all(), request.user, 'cuota__plan__unidad_educativa_id')
        if valores.get('unidad_educativa'):
            obligaciones = obligaciones.filter(cuota__plan__unidad_educativa_id=valores['unidad_educativa'])
        if valores.get('curso'):
            obligaciones = obligaciones.filter(estudiante__curso_id=valores['curso'])
        resultado = enviar_recordatorios_pago(obligaciones, valores['tipo'], valores['dias'])
        registrar_evento(
            accion='REPORTAR', entidad='OBLIGACION_PAGO', request=request, entidad_id='recordatorios-pago',
            cambios={'resultado': valores['tipo'], 'cantidad_filas': resultado['estudiantes_avisados']},
        )
        return Response({**resultado, 'fecha': timezone.now()}, status=status.HTTP_200_OK)


class AvisoPagoViewSet(mixins.ListModelMixin, GenericViewSet):
    """Bandeja de avisos de pago del usuario autenticado (pagos, becas, recordatorios)."""

    serializer_class = AvisoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = SchoolPagination

    def get_queryset(self):
        queryset = Notificacion.objects.filter(usuario=self.request.user, tipo__in=TIPOS_AVISO)
        params = self.request.query_params
        if params.get('leida') in ('true', 'false'):
            queryset = queryset.filter(leida=params['leida'] == 'true')
        if params.get('tipo'):
            queryset = queryset.filter(tipo=params['tipo'])
        return queryset.order_by('-fecha')

    @action(detail=False, methods=['get'])
    def resumen(self, request):
        return Response({'no_leidas': self.get_queryset().filter(leida=False).count()})

    @action(detail=True, methods=['post'])
    def leer(self, request, pk=None):
        aviso = self.get_object()
        if not aviso.leida:
            aviso.leida = True
            aviso.save(update_fields=['leida'])
        return Response(self.get_serializer(aviso).data)

    @action(detail=False, methods=['post'], url_path='leer-todas')
    def leer_todas(self, request):
        return Response({'marcadas': self.get_queryset().filter(leida=False).update(leida=True)})

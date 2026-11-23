from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from aplicaciones.usuarios.feature_access import FeaturePermission, SchoolPagination, scoped, id_filters, full_name
from aplicaciones.usuarios.tenancy import es_superadmin
from .models import Calificacion, CorreccionCalificacion
from .correcciones_services import solicitar_correccion, resolver_correccion


class PermisoCorreccion(FeaturePermission):
    model = 'correccion-nota'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if getattr(view, 'action', '') in ('aprobar', 'rechazar'):
            return es_superadmin(request.user) or hasattr(request.user, 'admin')
        return True


def grades_for(user):
    qs = scoped(Calificacion.objects.select_related('actividad__asignacion_docente__materia_curso__materia', 'actividad__periodo', 'historial_inscripcion__estudiante__usuario', 'historial_inscripcion__curso_nuevo'), user, 'historial_inscripcion__unidad_id')
    if es_superadmin(user) or hasattr(user, 'admin'):
        return qs  # Feature permissions still gate every administrative operation.
    if hasattr(user, 'profesor'):
        return qs.filter(actividad__asignacion_docente__profesor_id=user.profesor.pk)
    return qs.none()  # An incomplete teacher identity must never widen its scope.


class CalificacionConsultaSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.SerializerMethodField()
    actividad_nombre = serializers.CharField(source='actividad.nombre', read_only=True)
    curso_nombre = serializers.CharField(source='historial_inscripcion.curso_nuevo.nombre', read_only=True)
    materia_nombre = serializers.CharField(source='actividad.asignacion_docente.materia_curso.materia.nombre', read_only=True)
    periodo_nombre = serializers.CharField(source='actividad.periodo.nombre', read_only=True)
    puntaje_maximo = serializers.DecimalField(source='actividad.puntaje_maximo', max_digits=7, decimal_places=2, read_only=True)

    class Meta:
        model = Calificacion
        fields = ['id', 'valor', 'puntaje_maximo', 'estudiante_nombre', 'actividad_nombre', 'curso_nombre', 'materia_nombre', 'periodo_nombre']

    def get_estudiante_nombre(self, obj):
        return full_name(obj.historial_inscripcion.estudiante.usuario)


class CorreccionSerializer(serializers.ModelSerializer):
    detalle_calificacion = CalificacionConsultaSerializer(source='calificacion', read_only=True)
    solicitante_nombre = serializers.SerializerMethodField()
    autorizador_nombre = serializers.SerializerMethodField()

    class Meta:
        model = CorreccionCalificacion
        fields = ['id', 'calificacion', 'valor_anterior', 'valor_nuevo', 'motivo', 'estado', 'solicitado_por', 'autorizado_por', 'solicitado_at', 'resuelto_at', 'solicitante_nombre', 'autorizador_nombre', 'detalle_calificacion']
        read_only_fields = ['valor_anterior', 'estado', 'solicitado_por', 'autorizado_por', 'solicitado_at', 'resuelto_at']
        validators = []  # Domain service returns 409 for an existing pending request.

    def get_fields(self):
        fields = super().get_fields()
        fields['calificacion'].queryset = grades_for(self.context['request'].user)
        return fields

    def get_solicitante_nombre(self, obj):
        return full_name(obj.solicitado_por) or obj.solicitante_snapshot or ''

    def get_autorizador_nombre(self, obj):
        return full_name(obj.autorizado_por) or obj.autorizador_snapshot or ''

    def create(self, validated_data):
        return solicitar_correccion(request=self.context['request'], calificacion_id=validated_data['calificacion'].pk, valor_nuevo=validated_data['valor_nuevo'], motivo=validated_data['motivo'])


class CorreccionViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoCorreccion]
    pagination_class = SchoolPagination
    serializer_class = CorreccionSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs = CorreccionCalificacion.objects.filter(calificacion__in=grades_for(user)).select_related('calificacion__actividad__asignacion_docente__materia_curso__materia', 'calificacion__actividad__periodo', 'calificacion__historial_inscripcion__estudiante__usuario', 'calificacion__historial_inscripcion__curso_nuevo', 'solicitado_por', 'autorizado_por')
        if not es_superadmin(user) and not hasattr(user, 'admin'):
            qs = qs.filter(solicitado_por=user)
        params = self.request.query_params
        qs = id_filters(qs, params, {'estudiante': 'calificacion__historial_inscripcion__estudiante_id', 'periodo': 'calificacion__actividad__periodo_id', 'curso': 'calificacion__historial_inscripcion__curso_nuevo_id'})
        if params.get('estado'):
            if params['estado'] not in CorreccionCalificacion.Estado.values:
                raise serializers.ValidationError({'estado': 'Estado inválido.'})
            qs = qs.filter(estado=params['estado'])
        return qs.order_by('-solicitado_at', '-pk')

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        row = resolver_correccion(request=request, correccion_id=self.get_object().pk, aprobar=True)
        return Response(self.get_serializer(row).data)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        row = resolver_correccion(request=request, correccion_id=self.get_object().pk, aprobar=False)
        return Response(self.get_serializer(row).data)


class CalificacionCorregibleViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoCorreccion]
    pagination_class = SchoolPagination
    serializer_class = CalificacionConsultaSerializer

    def get_queryset(self):
        qs = grades_for(self.request.user).filter(actividad__periodo__estado='FIN', actividad__estado='ACTIVO', estado='REGISTRADA')
        return id_filters(qs, self.request.query_params, {'estudiante': 'historial_inscripcion__estudiante_id', 'curso': 'historial_inscripcion__curso_nuevo_id', 'periodo': 'actividad__periodo_id'}).order_by('pk')

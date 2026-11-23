from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from aplicaciones.usuarios.feature_access import FeaturePermission, SchoolPagination, scoped, id_filters, full_name
from aplicaciones.usuarios.auditoria import registrar_evento
from .models import IncidenteDisciplinario, AccionDisciplinaria, HistorialInscripcion, TutorEstudiante


class PermisoDisciplina(FeaturePermission):
    model = 'disciplina'


def enrollments(user):
    return scoped(HistorialInscripcion.objects.select_related('estudiante__usuario', 'curso_nuevo', 'unidad'), user, 'unidad_id')


def incidents(user):
    return scoped(IncidenteDisciplinario.objects.select_related('historial_inscripcion__estudiante__usuario', 'historial_inscripcion__curso_nuevo', 'historial_inscripcion__unidad', 'created_by'), user, 'historial_inscripcion__unidad_id')


class IncidenteSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.SerializerMethodField()
    curso_nombre = serializers.CharField(source='historial_inscripcion.curso_nuevo.nombre', read_only=True)
    responsable_nombre = serializers.SerializerMethodField()
    tipo = serializers.ChoiceField(choices=['OBSERVACION', 'FALTA'])
    severidad = serializers.ChoiceField(choices=['LEVE', 'MODERADA', 'GRAVE'])
    estado = serializers.ChoiceField(choices=['ABIERTO', 'CERRADO'], required=False)

    class Meta:
        model = IncidenteDisciplinario
        fields = ['id', 'historial_inscripcion', 'fecha', 'tipo', 'severidad', 'descripcion', 'estado', 'created_by', 'created_at', 'updated_at', 'estudiante_nombre', 'curso_nombre', 'responsable_nombre']
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_fields(self):
        fields = super().get_fields()
        fields['historial_inscripcion'].queryset = enrollments(self.context['request'].user)
        return fields

    def validate(self, attrs):
        enrollment = attrs.get('historial_inscripcion')
        if self.instance and enrollment and enrollment.pk != self.instance.historial_inscripcion_id:
            raise serializers.ValidationError({'historial_inscripcion': 'No se puede reasignar el incidente.'})
        return attrs

    def get_estudiante_nombre(self, obj):
        return full_name(obj.historial_inscripcion.estudiante.usuario)

    def get_responsable_nombre(self, obj):
        return full_name(obj.created_by) or obj.created_by_snapshot or ''


class CitacionSerializer(serializers.ModelSerializer):
    tutor_nombre = serializers.SerializerMethodField()
    responsable_nombre = serializers.SerializerMethodField()
    tutor_estudiante = serializers.PrimaryKeyRelatedField(queryset=TutorEstudiante.objects.none())
    fecha_programada = serializers.DateTimeField(required=True, allow_null=False)

    class Meta:
        model = AccionDisciplinaria
        fields = ['id', 'incidente', 'tutor_estudiante', 'fecha_programada', 'descripcion', 'resultado', 'estado', 'created_by', 'created_at', 'tutor_nombre', 'responsable_nombre']
        read_only_fields = ['estado', 'created_by', 'created_at']

    def get_fields(self):
        fields = super().get_fields()
        user = self.context['request'].user
        fields['incidente'].queryset = incidents(user)
        # Unit of enrollment is authoritative; the student's current unit can change.
        fields['tutor_estudiante'].queryset = TutorEstudiante.objects.filter(estudiante_id__in=enrollments(user).values('estudiante_id'))
        return fields

    def validate(self, attrs):
        incident = attrs.get('incidente', getattr(self.instance, 'incidente', None))
        tutor = attrs.get('tutor_estudiante', getattr(self.instance, 'tutor_estudiante', None))
        if self.instance:
            if self.instance.estado != 'PENDIENTE':
                raise serializers.ValidationError('Solo se editan citaciones pendientes.')
            if incident.pk != self.instance.incidente_id:
                raise serializers.ValidationError({'incidente': 'No se puede reasignar la citación.'})
        if tutor and incident and tutor.estudiante_id != incident.historial_inscripcion.estudiante_id:
            raise serializers.ValidationError({'tutor_estudiante': 'El tutor no corresponde al estudiante.'})
        return attrs

    def get_tutor_nombre(self, obj):
        return full_name(obj.tutor_estudiante.tutor.usuario) if obj.tutor_estudiante_id else ''

    def get_responsable_nombre(self, obj):
        return full_name(obj.created_by) or obj.created_by_snapshot or ''


class DisciplineBase(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoDisciplina]
    pagination_class = SchoolPagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def audit(self, obj, action_name, fields):
        incident = obj if isinstance(obj, IncidenteDisciplinario) else obj.incidente
        registrar_evento(accion=action_name, entidad='INCIDENTE_DISCIPLINARIO' if isinstance(obj, IncidenteDisciplinario) else 'CITACION_DISCIPLINARIA', entidad_id=obj.pk, request=self.request, unidad=incident.historial_inscripcion.unidad, cambios={'campos': fields})

    def perform_create(self, serializer):
        with transaction.atomic():
            extra = {'tipo': 'CITACION'} if isinstance(serializer, CitacionSerializer) else {}
            obj = serializer.save(created_by=self.request.user, created_by_snapshot=full_name(self.request.user), **extra)
            self.audit(obj, 'CREAR', serializer.validated_data.keys())

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            obj = self.get_queryset().select_for_update(of=('self',)).get(pk=self.get_object().pk)
            serializer = self.get_serializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            obj = serializer.save()
            self.audit(obj, 'ACTUALIZAR', serializer.validated_data.keys())
            return Response(serializer.data)


class IncidenteViewSet(DisciplineBase):
    serializer_class = IncidenteSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = id_filters(incidents(self.request.user), params, {'estudiante': 'historial_inscripcion__estudiante_id', 'historial_inscripcion': 'historial_inscripcion_id', 'gestion': 'fecha__year'})
        dates = {}
        for name, lookup in [('desde', 'fecha__date__gte'), ('hasta', 'fecha__date__lte')]:
            if params.get(name):
                try:
                    value = parse_date(params[name])
                except ValueError:
                    value = None
                if not value:
                    raise serializers.ValidationError({name: 'Fecha ISO inválida.'})
                dates[name] = value
                qs = qs.filter(**{lookup: value})
        if dates.get('desde') and dates.get('hasta') and dates['desde'] > dates['hasta']:
            raise serializers.ValidationError({'hasta': 'No puede preceder a desde.'})
        if params.get('estado'):
            if params['estado'] not in ('ABIERTO', 'CERRADO'):
                raise serializers.ValidationError({'estado': 'Estado inválido.'})
            qs = qs.filter(estado=params['estado'])
        return qs.order_by('-fecha', '-pk')


class CitacionViewSet(DisciplineBase):
    serializer_class = CitacionSerializer

    def get_queryset(self):
        qs = AccionDisciplinaria.objects.filter(tipo='CITACION', incidente__in=incidents(self.request.user)).select_related('incidente__historial_inscripcion__unidad', 'tutor_estudiante__tutor__usuario', 'created_by')
        return id_filters(qs, self.request.query_params, {'incidente': 'incidente_id', 'estudiante': 'incidente__historial_inscripcion__estudiante_id'}).order_by('-created_at', '-pk')

    @action(detail=True, methods=['post'])
    def estado(self, request, pk=None):
        with transaction.atomic():
            obj = self.get_queryset().select_for_update(of=('self',)).get(pk=self.get_object().pk)
            target = request.data.get('estado')
            allowed = {'PENDIENTE': {'ENTREGADA', 'ATENDIDA'}, 'ENTREGADA': {'ATENDIDA'}}
            if target not in allowed.get(obj.estado, set()):
                raise serializers.ValidationError({'estado': 'Transición no permitida.'})
            previous = obj.estado
            obj.estado = target
            obj.save(update_fields=['estado', 'updated_at'])
            registrar_evento(accion='ACTUALIZAR', entidad='CITACION_DISCIPLINARIA', entidad_id=obj.pk, request=request, unidad=obj.incidente.historial_inscripcion.unidad, cambios={'estado_anterior': previous, 'estado_nuevo': target})
            return Response(self.get_serializer(obj).data)


class InscripcionSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.SerializerMethodField()
    curso_nombre = serializers.CharField(source='curso_nuevo.nombre')

    class Meta:
        model = HistorialInscripcion
        fields = ['id', 'estudiante', 'estudiante_nombre', 'curso_nombre', 'fecha_inscripcion']

    def get_estudiante_nombre(self, obj):
        return full_name(obj.estudiante.usuario)


class TutorConsultaSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()

    class Meta:
        model = TutorEstudiante
        fields = ['id', 'nombre', 'es_principal']

    def get_nombre(self, obj):
        return full_name(obj.tutor.usuario)


class InscripcionDisciplinaViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoDisciplina]
    pagination_class = SchoolPagination
    serializer_class = InscripcionSerializer

    def get_queryset(self):
        qs = id_filters(enrollments(self.request.user), self.request.query_params, {'estudiante': 'estudiante_id', 'gestion': 'fecha_inscripcion__year'})
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(estudiante__usuario__nombre__icontains=search) | Q(estudiante__usuario__apellido__icontains=search))
        return qs.order_by('-fecha_inscripcion', '-pk')


class TutorDisciplinaViewSet(InscripcionDisciplinaViewSet):
    serializer_class = TutorConsultaSerializer

    def get_queryset(self):
        pk = serializers.IntegerField(min_value=1).run_validation(self.request.query_params.get('historial_inscripcion'))
        enrollment = enrollments(self.request.user).filter(pk=pk).first()
        if not enrollment:
            raise serializers.ValidationError({'historial_inscripcion': 'Inscripción no disponible.'})
        return TutorEstudiante.objects.filter(estudiante_id=enrollment.estudiante_id).select_related('tutor__usuario').order_by('-es_principal', 'pk')

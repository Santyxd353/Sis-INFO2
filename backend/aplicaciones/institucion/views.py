from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from rest_framework_simplejwt.authentication import JWTAuthentication
from aplicaciones.usuarios.permissions import PermisoPorPuesto
from aplicaciones.usuarios.auditoria import registrar_evento
from aplicaciones.usuarios.feature_access import SchoolPagination, granted, id_filters, scoped
from aplicaciones.usuarios.tenancy import es_superadmin, resolver_alcance, unidades_permitidas, validar_unidad

from .models import Aula, Colegio, Modulo, UnidadEducativa
from .serializers import AulaSerializer, ColegioSerializer, ModuloSerializer, UnidadEducativaSerializer


class BaseGestionViewSet(ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoPorPuesto]


class ColegioViewSet(BaseGestionViewSet):
    queryset = Colegio.objects.all().order_by('nombre')
    serializer_class = ColegioSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        alcance = resolver_alcance(self.request.user)
        if alcance['tipo'] == 'GLOBAL':
            return queryset
        return queryset.filter(pk=alcance['colegio_id'])


class UnidadEducativaViewSet(BaseGestionViewSet):
    queryset = UnidadEducativa.objects.select_related('colegio').all().order_by('nombre')
    serializer_class = UnidadEducativaSerializer
    pagination_class = SchoolPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        colegio_param = self.request.query_params.get('colegio')
        colegio_id = None
        if colegio_param is not None:
            try:
                colegio_id = int(colegio_param)
            except (TypeError, ValueError):
                raise ValidationError({'colegio': 'Debe ser un entero positivo.'})
            if colegio_id <= 0:
                raise ValidationError({'colegio': 'Debe ser un entero positivo.'})
        permitidas = unidades_permitidas(self.request.user)
        if permitidas is None:
            return queryset.filter(colegio_id=colegio_id) if colegio_id else queryset
        alcance = resolver_alcance(self.request.user)
        if colegio_id is not None and colegio_id != alcance['colegio_id']:
            raise PermissionDenied('No puede consultar unidades de otro colegio.')
        queryset = queryset.filter(id__in=permitidas)
        return queryset.filter(colegio_id=colegio_id) if colegio_id else queryset

    def perform_update(self, serializer):
        colegio = serializer.validated_data.get('colegio', serializer.instance.colegio)
        validar_unidad(self.request.user, serializer.instance)
        if colegio != serializer.instance.colegio:
            raise PermissionDenied('No puede trasladar la unidad educativa a otro colegio.')
        serializer.save()

    def perform_create(self, serializer):
        colegio = serializer.validated_data.get('colegio')
        alcance = resolver_alcance(self.request.user)
        if alcance['tipo'] != 'GLOBAL' and (
            alcance['tipo'] != 'COLEGIO' or colegio is None
            or colegio.pk != alcance['colegio_id']
        ):
            raise PermissionDenied('No puede crear unidades fuera de su colegio.')
        # Límites de unidades educativas del plan vigente (HU-SE01 regla 6).
        from aplicaciones.suscripciones.servicios import validar_limite_unidades
        validar_limite_unidades(colegio)
        serializer.save()


class InfraestructuraPermission(BasePermission):
    """Uses effective permission records; SuperAdmin has read-only support access."""

    def has_permission(self, request, view):
        action = 'desactivar' if getattr(view, 'action', None) == 'desactivar' else {
            'POST': 'crear', 'PUT': 'editar', 'PATCH': 'editar',
        }.get(request.method, 'listar')
        if es_superadmin(request.user):
            return action == 'listar'
        return granted(request.user, view.recurso, action)


class InfraestructuraBaseViewSet(ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [InfraestructuraPermission]
    pagination_class = SchoolPagination
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    recurso = ''

    def _validate_query_scope(self, queryset, mapping):
        return id_filters(queryset, self.request.query_params, mapping)

    def _validate_unit_write(self, unit):
        validar_unidad(self.request.user, unit)


class ModuloViewSet(InfraestructuraBaseViewSet):
    serializer_class = ModuloSerializer
    recurso = 'modulo'
    queryset = Modulo.objects.select_related('unidad_educativa__colegio', 'colegio_fk')

    def get_queryset(self):
        queryset = self.queryset.all()
        permitted = unidades_permitidas(self.request.user)
        if permitted is not None:
            queryset = queryset.filter(unidad_educativa_id__in=permitted)
        queryset = self._validate_query_scope(queryset, {
            'unidad_educativa': 'unidad_educativa_id',
            'colegio': 'unidad_educativa__colegio_id',
        })
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado.upper())
        name = self.request.query_params.get('nombre', '').strip()
        if name:
            queryset = queryset.filter(nombre__icontains=name)
        return queryset.order_by('nombre', 'pk')

    def perform_create(self, serializer):
        unit = serializer.validated_data['unidad_educativa']
        self._validate_unit_write(unit)
        serializer.save(colegio_fk=unit.colegio)
        row = serializer.instance
        registrar_evento(accion='CREAR', entidad='MODULO_FISICO', entidad_id=row.pk,
            request=self.request, unidad=unit, cambios={'campos': list(serializer.validated_data)})

    def perform_update(self, serializer):
        unit = serializer.validated_data.get('unidad_educativa', serializer.instance.unidad_educativa)
        self._validate_unit_write(unit)
        serializer.save(colegio_fk=unit.colegio)
        row = serializer.instance
        registrar_evento(accion='ACTUALIZAR', entidad='MODULO_FISICO', entidad_id=row.pk,
            request=self.request, unidad=unit, cambios={'campos': list(serializer.validated_data)})

    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        row = self.get_object()
        self._validate_unit_write(row.unidad_educativa)
        if row.aulas.filter(estado=True, eliminado_at__isnull=True).exists():
            raise ValidationError({'detalle': 'No puede desactivar un módulo con aulas activas.'})
        row.estado = Modulo.Estado.INACTIVO
        row.eliminado_at = timezone.now()
        row.save(update_fields=['estado', 'eliminado_at'])
        registrar_evento(accion='DESACTIVAR', entidad='MODULO_FISICO', entidad_id=row.pk,
            request=request, unidad=row.unidad_educativa, cambios={'campos': ['estado', 'eliminado_at']})
        return Response(self.get_serializer(row).data)


class AulaViewSet(InfraestructuraBaseViewSet):
    serializer_class = AulaSerializer
    recurso = 'aula'
    queryset = Aula.objects.select_related('modulo__unidad_educativa__colegio')

    def get_queryset(self):
        queryset = self.queryset.all()
        permitted = unidades_permitidas(self.request.user)
        if permitted is not None:
            queryset = queryset.filter(modulo__unidad_educativa_id__in=permitted)
        # A teacher can only see rooms already used by their own schedules.
        if not es_superadmin(self.request.user) and not hasattr(self.request.user, 'admin'):
            profesor = getattr(self.request.user, 'profesor', None)
            queryset = queryset.filter(horarios_clase__profesor=profesor).distinct() if profesor else queryset.none()
        queryset = self._validate_query_scope(queryset, {
            'unidad_educativa': 'modulo__unidad_educativa_id',
            'modulo': 'modulo_id',
            'colegio': 'modulo__unidad_educativa__colegio_id',
        })
        state = self.request.query_params.get('estado')
        if state:
            value = state.strip().upper()
            if value not in {'ACTIVO', 'INACTIVO'}:
                raise ValidationError({'estado': 'Use ACTIVO o INACTIVO.'})
            queryset = queryset.filter(estado=value == 'ACTIVO')
        kind = self.request.query_params.get('tipo')
        if kind:
            queryset = queryset.filter(tipo=kind.upper())
        name = self.request.query_params.get('nombre', '').strip()
        if name:
            queryset = queryset.filter(nombre__icontains=name)
        return queryset.order_by('nombre', 'pk')

    def _write_module(self, module):
        if (module.estado != Modulo.Estado.ACTIVO or module.eliminado_at is not None
                or module.unidad_educativa_id is None):
            raise ValidationError({'modulo': 'Seleccione un módulo activo y conciliado con una unidad educativa.'})
        self._validate_unit_write(module.unidad_educativa)

    def perform_create(self, serializer):
        module = serializer.validated_data['modulo']
        self._write_module(module)
        serializer.save()
        row = serializer.instance
        registrar_evento(accion='CREAR', entidad='AULA', entidad_id=row.pk,
            request=self.request, unidad=module.unidad_educativa, cambios={'campos': list(serializer.validated_data)})

    def perform_update(self, serializer):
        module = serializer.validated_data.get('modulo', serializer.instance.modulo)
        self._write_module(module)
        serializer.save()
        row = serializer.instance
        registrar_evento(accion='ACTUALIZAR', entidad='AULA', entidad_id=row.pk,
            request=self.request, unidad=module.unidad_educativa, cambios={'campos': list(serializer.validated_data)})

    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        row = self.get_object()
        self._write_module(row.modulo)
        if row.horarios_clase.filter(estado='ACTIVO').filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=timezone.localdate())
        ).exists():
            raise ValidationError({'detalle': 'No puede desactivar un aula con horarios vigentes.'})
        row.estado = False
        row.eliminado_at = timezone.now()
        row.save(update_fields=['estado', 'eliminado_at'])
        registrar_evento(accion='DESACTIVAR', entidad='AULA', entidad_id=row.pk,
            request=request, unidad=row.modulo.unidad_educativa, cambios={'campos': ['estado', 'eliminado_at']})
        return Response(self.get_serializer(row).data)

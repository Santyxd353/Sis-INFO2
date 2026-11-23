from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission

from aplicaciones.institucion.models import UnidadEducativa

from .models import EventoAuditoria
from .models import PermisoPuesto
from .tenancy import es_superadmin, resolver_alcance


class PermisoConsultaAuditoria(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        if not getattr(usuario, 'is_authenticated', False):
            return False
        if es_superadmin(usuario):
            return True
        if not hasattr(usuario, 'admin') or not usuario.admin.puesto_id:
            return False
        return PermisoPuesto.objects.filter(
            puesto_id=usuario.admin.puesto_id,
            modelo__nombre__in=('auditoria', 'evento-auditoria'),
            accion__nombre='listar',
        ).exists()


class EventoAuditoriaSerializer(serializers.ModelSerializer):
    actor_username = serializers.SerializerMethodField()
    actor_rol = serializers.SerializerMethodField()

    def _actor(self, obj):
        cache = self.context.setdefault('_actores_auditoria', {})
        if obj.usuario not in cache:
            from .models import Usuario
            cache[obj.usuario] = Usuario.objects.select_related('rol').filter(pk=obj.usuario).first() if obj.usuario else None
        return cache[obj.usuario]

    def get_actor_username(self, obj):
        actor = self._actor(obj)
        return actor.username if actor else None

    def get_actor_rol(self, obj):
        actor = self._actor(obj)
        return actor.rol.nombre if actor and actor.rol_id else None

    class Meta:
        model = EventoAuditoria
        fields = (
            'id', 'ambito', 'colegio', 'unidad_educativa', 'usuario',
            'actor_snapshot', 'actor_username', 'actor_rol', 'accion', 'entidad', 'entidad_id',
            'cambios_sanitizados', 'ip_hash', 'correlacion', 'fecha_cliente',
            'zona_cliente', 'created_at',
        )
        read_only_fields = fields


class AuditoriaPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class EventoAuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EventoAuditoriaSerializer
    permission_classes = [PermisoConsultaAuditoria]
    pagination_class = AuditoriaPagination
    http_method_names = ['get', 'head', 'options']

    def _alcance(self):
        usuario = self.request.user
        alcance = resolver_alcance(usuario)
        if alcance['tipo'] == 'GLOBAL':
            return None, None, False
        if not hasattr(usuario, 'admin'):
            raise PermissionDenied('No tiene permiso para consultar la auditoría.')
        return (
            alcance['colegio_id'], alcance['unidad_id'], alcance['tipo'] == 'UNIDAD',
        )

    @staticmethod
    def _id_positivo(valor, nombre):
        if valor in (None, ''):
            return None
        try:
            convertido = int(valor)
        except (TypeError, ValueError):
            raise ValidationError({nombre: 'Debe ser un entero positivo.'})
        if convertido <= 0:
            raise ValidationError({nombre: 'Debe ser un entero positivo.'})
        return convertido

    @staticmethod
    def _fecha(valor, nombre, fin=False):
        if not valor:
            return None
        fecha = parse_date(valor) if len(valor) == 10 else None
        if fecha is not None:
            fecha_hora = datetime.combine(fecha, time.max if fin else time.min)
        else:
            fecha_hora = parse_datetime(valor)
            if fecha_hora is None:
                raise ValidationError({nombre: 'Use una fecha ISO 8601 válida.'})
        if timezone.is_naive(fecha_hora):
            fecha_hora = timezone.make_aware(fecha_hora)
        return fecha_hora

    def get_queryset(self):
        colegio_permitido, unidad_permitida, solo_unidad = self._alcance()
        queryset = EventoAuditoria.objects.select_related(
            'colegio', 'unidad_educativa',
        ).order_by('-created_at', '-pk')

        if colegio_permitido is not None:
            if solo_unidad:
                queryset = queryset.filter(unidad_educativa_id=unidad_permitida)
            else:
                queryset = queryset.filter(colegio_id=colegio_permitido)

        params = self.request.query_params
        usuario_id = self._id_positivo(params.get('usuario'), 'usuario')
        colegio_id = self._id_positivo(params.get('colegio'), 'colegio')
        unidad_id = self._id_positivo(params.get('unidad'), 'unidad')
        desde = self._fecha(params.get('desde'), 'desde')
        hasta = self._fecha(params.get('hasta'), 'hasta', fin=True)
        if desde and hasta and desde > hasta:
            raise ValidationError({'hasta': 'Debe ser posterior o igual a desde.'})

        if colegio_id is not None:
            if colegio_permitido is not None and colegio_id != colegio_permitido:
                raise PermissionDenied('No puede consultar otro colegio.')
            queryset = queryset.filter(colegio_id=colegio_id)
        if unidad_id is not None:
            unidad = UnidadEducativa.objects.filter(pk=unidad_id).only('colegio_id').first()
            if unidad is None:
                raise ValidationError({'unidad': 'La unidad no existe.'})
            if colegio_permitido is not None and unidad.colegio_id != colegio_permitido:
                raise PermissionDenied('No puede consultar una unidad de otro colegio.')
            if solo_unidad and unidad_id != unidad_permitida:
                raise PermissionDenied('No puede consultar otra unidad.')
            queryset = queryset.filter(unidad_educativa_id=unidad_id)
        if usuario_id is not None:
            queryset = queryset.filter(usuario=usuario_id)
        if params.get('accion'):
            queryset = queryset.filter(accion=params['accion'].strip().upper())
        if params.get('entidad'):
            queryset = queryset.filter(entidad=params['entidad'].strip().upper())
        if desde:
            queryset = queryset.filter(created_at__gte=desde)
        if hasta:
            queryset = queryset.filter(created_at__lte=hasta)
        return queryset

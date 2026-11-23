from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import PermissionDenied

from rest_framework_simplejwt.authentication import JWTAuthentication
from aplicaciones.usuarios.permissions import PermisoPorPuesto
from aplicaciones.usuarios.tenancy import unidades_permitidas, validar_unidad
from aplicaciones.usuarios.feature_access import id_filters

from .models import CalendarioAcademico, Feriado, Periodo, TipoFeriado
from .serializers import (
    CalendarioAcademicoSerializer,
    FeriadoSerializer,
    PeriodoSerializer,
    TipoFeriadoSerializer,
)


class BaseLecturaViewSet(ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoPorPuesto]


class CalendarioAcademicoViewSet(BaseLecturaViewSet):
    queryset = CalendarioAcademico.objects.select_related('unidad_educativa').all()
    serializer_class = CalendarioAcademicoSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        permitidas = unidades_permitidas(self.request.user)
        if permitidas is not None:
            queryset = queryset.filter(unidad_educativa_id__in=permitidas)
        return id_filters(queryset, self.request.query_params, {
            'unidad_educativa': 'unidad_educativa_id',
        })

    def _validar_unidad(self, unidad):
        validar_unidad(self.request.user, unidad)

    def perform_create(self, serializer):
        self._validar_unidad(serializer.validated_data['unidad_educativa'])
        serializer.save()

    def perform_update(self, serializer):
        unidad = serializer.validated_data.get(
            'unidad_educativa', serializer.instance.unidad_educativa
        )
        self._validar_unidad(unidad)
        serializer.save()


class PeriodoViewSet(BaseLecturaViewSet):
    queryset = Periodo.objects.select_related('calendario', 'calendario__unidad_educativa').all()
    serializer_class = PeriodoSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        permitidas = unidades_permitidas(self.request.user)
        if permitidas is None:
            return queryset
        return queryset.filter(calendario__unidad_educativa_id__in=permitidas)

    def _validar_calendario(self, calendario):
        validar_unidad(self.request.user, calendario.unidad_educativa)

    def perform_create(self, serializer):
        self._validar_calendario(serializer.validated_data['calendario'])
        serializer.save()

    def perform_update(self, serializer):
        calendario = serializer.validated_data.get('calendario', serializer.instance.calendario)
        self._validar_calendario(calendario)
        serializer.save()


class TipoFeriadoViewSet(BaseLecturaViewSet):
    queryset = TipoFeriado.objects.all()
    serializer_class = TipoFeriadoSerializer


class FeriadoViewSet(BaseLecturaViewSet):
    queryset = Feriado.objects.select_related(
        'calendario', 'calendario__unidad_educativa', 'tipo'
    ).all()
    serializer_class = FeriadoSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        permitidas = unidades_permitidas(self.request.user)
        if permitidas is None:
            return queryset
        return queryset.filter(calendario__unidad_educativa_id__in=permitidas)

    def _validar_calendario(self, calendario):
        validar_unidad(self.request.user, calendario.unidad_educativa)

    def perform_create(self, serializer):
        self._validar_calendario(serializer.validated_data['calendario'])
        serializer.save()

    def perform_update(self, serializer):
        calendario = serializer.validated_data.get('calendario', serializer.instance.calendario)
        self._validar_calendario(calendario)
        serializer.save()

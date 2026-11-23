from rest_framework.viewsets import ModelViewSet

from rest_framework_simplejwt.authentication import JWTAuthentication
from aplicaciones.usuarios.permissions import PermisoPorPuesto, PermisoPorRol
from aplicaciones.usuarios.tenancy import unidades_permitidas
from aplicaciones.usuarios.feature_access import id_filters

from .models import Profesor
from .serializers import GestionProfesorSerializer, ProfesorSerializer


class ProfesorViewSet(ModelViewSet):
    queryset = Profesor.objects.select_related('usuario', 'usuario__rol', 'unidad').all().order_by(
        'usuario__apellido', 'usuario__nombre'
    )
    serializer_class = ProfesorSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoPorPuesto & PermisoPorRol]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return GestionProfesorSerializer
        return ProfesorSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        permitidas = unidades_permitidas(self.request.user)
        if permitidas is not None:
            queryset = queryset.filter(unidad_id__in=permitidas)
        return id_filters(queryset, self.request.query_params, {
            'unidad': 'unidad_id',
        })

    def perform_destroy(self, instance):
        # El perfil docente y sus credenciales forman una sola cuenta.
        instance.usuario.delete()

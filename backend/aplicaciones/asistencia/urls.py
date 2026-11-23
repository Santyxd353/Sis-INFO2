from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegistroAsistenciaViewSet, DetalleAsistenciaViewSet

router = DefaultRouter()
router.register(r'registros', RegistroAsistenciaViewSet, basename='registro-asistencia')
router.register(r'detalles', DetalleAsistenciaViewSet, basename='detalle-asistencia')

urlpatterns = [
    path('', include(router.urls)),
]

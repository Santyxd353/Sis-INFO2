from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HistorialEstudianteViewSet, NotaViewSet, RiesgoAcademicoViewSet,
    ConfiguracionRiesgoViewSet, AlertaViewSet,
)

router = DefaultRouter()
router.register(r'historial', HistorialEstudianteViewSet, basename='historial')
router.register(r'notas', NotaViewSet, basename='nota')
router.register(r'riesgos', RiesgoAcademicoViewSet, basename='riesgo')
router.register(r'configuracion', ConfiguracionRiesgoViewSet, basename='configuracion')
router.register(r'alertas', AlertaViewSet, basename='alertas')

urlpatterns = [
    path('', include(router.urls)),
]

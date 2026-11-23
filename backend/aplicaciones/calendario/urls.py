from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CalendarioAcademicoViewSet, FeriadoViewSet, PeriodoViewSet, TipoFeriadoViewSet


router = DefaultRouter()
router.register('calendarios', CalendarioAcademicoViewSet, basename='calendario')
router.register('periodos', PeriodoViewSet, basename='periodo')
router.register('tipos-feriado', TipoFeriadoViewSet, basename='tipo-feriado')
router.register('feriados', FeriadoViewSet, basename='feriado')

urlpatterns = [
    path('', include(router.urls)),
]

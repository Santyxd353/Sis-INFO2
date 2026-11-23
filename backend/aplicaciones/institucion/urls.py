from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AulaViewSet, ColegioViewSet, ModuloViewSet, UnidadEducativaViewSet


router = DefaultRouter()
router.register('colegios', ColegioViewSet, basename='colegio')
router.register('unidades-educativas', UnidadEducativaViewSet, basename='unidad-educativa')
router.register('modulos', ModuloViewSet, basename='modulo')
router.register('aulas', AulaViewSet, basename='aula')

urlpatterns = [
    path('', include(router.urls)),
]

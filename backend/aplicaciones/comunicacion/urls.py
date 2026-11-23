from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AvisoViewSet, ComunicadoViewSet, alertas_api, preferencias_api

router = DefaultRouter()
router.register('comunicados', ComunicadoViewSet, basename='comunicado')
router.register('notificaciones', AvisoViewSet, basename='aviso-comunicacion')
urlpatterns = [path('', include(router.urls)), path('preferencias/', preferencias_api), path('alertas/', alertas_api)]

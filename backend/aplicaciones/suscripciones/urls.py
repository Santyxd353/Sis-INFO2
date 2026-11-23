from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MetodoPagoColegioViewSet, MetodoPagoViewSet, MetodosPagoPublicosView, PagoViewSet,
    PlanViewSet, PlanesPublicosView, SuscripcionViewSet, notificacion_stripe, notificacion_vendis,
)

router = DefaultRouter()
router.register(r'planes', PlanViewSet, basename='plan')
router.register(r'suscripciones', SuscripcionViewSet, basename='suscripcion')
router.register(r'pagos', PagoViewSet, basename='pago')
router.register(r'metodos-pago', MetodoPagoViewSet, basename='metodo-pago')
router.register(r'metodos-pago-colegio', MetodoPagoColegioViewSet, basename='metodo-pago-colegio')

urlpatterns = [
    path('planes-publicos/', PlanesPublicosView.as_view(), name='planes-publicos'),
    path('metodos-pago-publicos/', MetodosPagoPublicosView.as_view(), name='metodos-pago-publicos'),
    path('vendis/webhook/', notificacion_vendis, name='notificacion-vendis'),
    path('stripe/webhook/', notificacion_stripe, name='notificacion-stripe'),
    path('', include(router.urls)),
]

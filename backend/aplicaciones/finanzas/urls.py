from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AsignacionBecaViewSet, BecaViewSet, EstadoCuentaView, MorosidadView, ObligacionPagoViewSet, PagoViewSet,
    PlanPagoViewSet, SimulacionTributariaView,
)
from .views_avisos import AvisoPagoViewSet, RecordatoriosPagoView
from .views_qr import ConciliacionQRView, SolicitudQRViewSet, qr_simulado

router = DefaultRouter()
router.register('planes-pago', PlanPagoViewSet, basename='plan-pago')
router.register('becas', BecaViewSet, basename='beca')
router.register('asignaciones-beca', AsignacionBecaViewSet, basename='asignacion-beca')
router.register('obligaciones', ObligacionPagoViewSet, basename='obligacion-pago')
router.register('pagos', PagoViewSet, basename='pago')
router.register('solicitudes-qr', SolicitudQRViewSet, basename='pago-qr')
router.register('avisos', AvisoPagoViewSet, basename='aviso-pago')

urlpatterns = [
    path('estado-cuenta/', EstadoCuentaView.as_view(), name='estado-cuenta'),
    path('morosidad/', MorosidadView.as_view(), name='morosidad'),
    path('simulacion-tributaria/', SimulacionTributariaView.as_view(), name='simulacion-tributaria'),
    path('conciliacion-qr/', ConciliacionQRView.as_view(), name='conciliacion-qr'),
    path('recordatorios-pago/', RecordatoriosPagoView.as_view(), name='recordatorios-pago'),
    path('qr-simulado/<str:qr_id>.png', qr_simulado, name='qr-simulado'),
    path('', include(router.urls)),
]

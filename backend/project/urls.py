from django.contrib import admin
from django.urls import path, include
from .health import healthz

urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('admin/', admin.site.urls),
    path('api/usuarios/', include('aplicaciones.usuarios.urls')),
    path('api/estudiantes/', include('aplicaciones.estudiantes.urls')),
    path('api/academico/', include('aplicaciones.academico.urls')),
    path('api/personal/', include('aplicaciones.personal.urls')),
    path('api/institucion/', include('aplicaciones.institucion.urls')),
    path('api/calendario/', include('aplicaciones.calendario.urls')),
    path('api/asistencia/', include('aplicaciones.asistencia.urls')),
    path('api/comunicacion/', include('aplicaciones.comunicacion.urls')),
    path('api/portal/', include('aplicaciones.portal.urls')),
    path('api/seguimiento/', include('aplicaciones.seguimiento_academico.urls')),
    path('api/reportes/', include('aplicaciones.reportes.urls')),
    path('api/suscripciones/', include('aplicaciones.suscripciones.urls')),
    path('api/respaldos/', include('aplicaciones.respaldos.urls')),
    path('api/finanzas/', include('aplicaciones.finanzas.urls')),
]

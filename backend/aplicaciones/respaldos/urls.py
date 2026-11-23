from django.urls import path
from . import views

urlpatterns = [
    path('', views.respaldos),
    path('configuracion/', views.configuracion),
    path('estado-procesador/', views.estado_procesador),
    path('<uuid:pk>/', views.detalle),
    path('<uuid:pk>/descargar/', views.descargar),
]

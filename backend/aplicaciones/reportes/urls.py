from django.urls import path
from . import views

urlpatterns = [
    path('voz/interpretar/', views.VozInterpretar.as_view()),
    path('voz/ejecutar/', views.VozEjecutar.as_view()),
    path('analitica/resumen/', views.AnaliticaResumen.as_view()),
    path('analitica/exportar/', views.AnaliticaExportar.as_view()),
    path('ejecuciones/', views.Ejecuciones.as_view()),
    path('ejecuciones/<uuid:pk>/', views.EjecucionDetalle.as_view()),
    path('ejecuciones/<uuid:pk>/descargar/', views.EjecucionDescargar.as_view()),
    path('ejecuciones/<uuid:pk>/archivar/', views.EjecucionArchivar.as_view()),
    path('catalogo/', views.Catalogo.as_view()),
    path('catalogo/<str:codigo>/', views.Catalogo.as_view()),
    path('definiciones/', views.Definiciones.as_view()),
    path('definiciones/<int:pk>/', views.DefinicionDetalle.as_view()),
    path('definiciones/<int:pk>/archivar/', views.Archivar.as_view()),
    path('previsualizar/', views.Previsualizar.as_view()),
    path('exportar/', views.Exportar.as_view()),
    path('qbe/catalogo/', views.QbeCatalogo.as_view()),
    path('qbe/catalogo/<str:codigo>/', views.QbeCatalogo.as_view()),
    path('qbe/definiciones/', views.QbeDefiniciones.as_view()),
    path('qbe/definiciones/<int:pk>/', views.QbeDefinicionDetalle.as_view()),
    path('qbe/definiciones/<int:pk>/archivar/', views.QbeArchivar.as_view()),
    path('qbe/previsualizar/', views.QbePrevisualizar.as_view()),
    path('qbe/exportar/', views.QbeExportar.as_view()),
]

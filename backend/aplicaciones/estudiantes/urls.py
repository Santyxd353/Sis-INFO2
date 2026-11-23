from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .disciplina_api import (
    CitacionViewSet,
    IncidenteViewSet,
    InscripcionDisciplinaViewSet,
    TutorDisciplinaViewSet,
)
from .views import (
    DocumentoAcademicoEmitidoViewSet,
    EstudianteViewSet,
    MisResultadosView,
    TutorEstudianteViewSet,
    TutorViewSet,
)


router = DefaultRouter()
router.register('incidentes', IncidenteViewSet, basename='disciplina-incidente')
router.register('citaciones', CitacionViewSet, basename='disciplina-citacion')
router.register('inscripciones-disciplina', InscripcionDisciplinaViewSet, basename='disciplina-inscripcion')
router.register('tutores-disciplina', TutorDisciplinaViewSet, basename='disciplina-tutor')
router.register('estudiantes', EstudianteViewSet, basename='estudiante')
router.register('tutores', TutorViewSet, basename='tutor')
router.register('relaciones', TutorEstudianteViewSet, basename='tutor-estudiante')
router.register(
    'documentos-academicos', DocumentoAcademicoEmitidoViewSet, basename='documento-academico',
)

urlpatterns = [
    path('mis-resultados/', MisResultadosView.as_view(), name='mis-resultados'),
    path('', include(router.urls)),
]

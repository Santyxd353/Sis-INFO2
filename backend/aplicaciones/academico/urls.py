from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .correcciones_api import CorreccionViewSet, CalificacionCorregibleViewSet
from .horarios_api import (HorarioViewSet, HorarioAsignacionViewSet, HorarioAulaViewSet,
                          HorarioCursoViewSet, HorarioProfesorViewSet)

from .views import (
    ActividadEvaluacionViewSet, AsignacionDocenteViewSet, CalificacionViewSet,
    ConfiguracionEvaluacionViewSet, CursoViewSet, GradoViewSet,
    MateriaCursoConsultaViewSet, MateriaViewSet, ParaleloViewSet,
)


router = DefaultRouter()
router.register('horarios', HorarioViewSet, basename='horario')
router.register('horarios-asignaciones', HorarioAsignacionViewSet, basename='horario-asignacion')
router.register('horarios-aulas', HorarioAulaViewSet, basename='horario-aula')
router.register('horarios-cursos', HorarioCursoViewSet, basename='horario-curso')
router.register('horarios-profesores', HorarioProfesorViewSet, basename='horario-profesor')
router.register('correcciones', CorreccionViewSet, basename='correccion-nota')
router.register('calificaciones-corregibles', CalificacionCorregibleViewSet, basename='calificacion-corregible')
router.register('grados', GradoViewSet, basename='grado')
router.register('paralelos', ParaleloViewSet, basename='paralelo')
router.register('cursos', CursoViewSet, basename='curso')
router.register('materias', MateriaViewSet, basename='materia')
router.register(
    'asignaciones-docentes', AsignacionDocenteViewSet,
    basename='asignacion-docente',
)
router.register(
    'materias-curso', MateriaCursoConsultaViewSet,
    basename='materia-curso',
)
router.register(
    'configuraciones-evaluacion', ConfiguracionEvaluacionViewSet,
    basename='configuracion-evaluacion',
)
router.register(
    'actividades-evaluacion', ActividadEvaluacionViewSet,
    basename='actividad-evaluacion',
)
router.register('calificaciones', CalificacionViewSet, basename='calificacion')

urlpatterns = [
    path('', include(router.urls)),
]

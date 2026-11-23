"""Catálogo declarativo; las rutas internas nunca forman parte de su representación pública.

Riesgo se excluye hasta resolver su contexto histórico de inscripción.
"""
from django.apps import apps

_FUENTES = {
    'ESTUDIANTES_INSCRITOS': ('estudiantes', 'HistorialInscripcion', ('estudiante', 'curso', 'estado')),
    'ASISTENCIA_RESUMEN': ('estudiantes', 'AsistenciaEstudiante', ('estudiante', 'fecha', 'estado')),
    'RENDIMIENTO_ACADEMICO': ('academico', 'ResultadoTrimestral', ('estudiante', 'materia', 'periodo')),
    'INCIDENTES_DISCIPLINARIOS': ('estudiantes', 'IncidenteDisciplinario', ('estudiante', 'tipo', 'estado')),
}


def catalogo_publico():
    from .fuentes_operativas import catalogo_operativo
    return catalogo_operativo()


def resolver_fuente(codigo):
    """Solo acepta un código predefinido; no recibe nombres de modelos del cliente."""
    app, modelo, _ = _FUENTES[codigo]
    return apps.get_model(app, modelo)

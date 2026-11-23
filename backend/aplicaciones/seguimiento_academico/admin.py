from django.contrib import admin

from .models import HistorialEstudiante, Nota, RiesgoAcademico, ConfiguracionRiesgo


class NotaInline(admin.TabularInline):
    model = Nota
    extra = 0


@admin.register(HistorialEstudiante)
class HistorialEstudianteAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'periodo', 'curso', 'promedio')
    list_filter = ('periodo', 'curso')
    inlines = [NotaInline]


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ('historial', 'materia', 'tipo_evaluacion', 'nota', 'ponderacion')
    list_filter = ('tipo_evaluacion', 'materia')


@admin.register(RiesgoAcademico)
class RiesgoAcademicoAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'periodo', 'nivel', 'activo', 'responsable', 'fecha_evaluacion')
    list_filter = ('nivel', 'activo', 'periodo')
    search_fields = ('estudiante__usuario__nombre', 'estudiante__usuario__apellido', 'motivo')


@admin.register(ConfiguracionRiesgo)
class ConfiguracionRiesgoAdmin(admin.ModelAdmin):
    list_display = (
        'unidad', 'umbral_rendimiento', 'umbral_riesgo_alto',
        'umbral_inasistencia', 'porcentaje_minimo_asistencia', 'activo',
    )
    list_filter = ('activo',)

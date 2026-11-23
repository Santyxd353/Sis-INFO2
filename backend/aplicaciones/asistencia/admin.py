from django.contrib import admin

from .models import RegistroAsistencia, DetalleAsistencia


class DetalleAsistenciaInline(admin.TabularInline):
    model = DetalleAsistencia
    extra = 0


@admin.register(RegistroAsistencia)
class RegistroAsistenciaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'asignacion', 'periodo', 'docente', 'observacion')
    list_filter = ('fecha', 'periodo', 'asignacion__curso')
    inlines = [DetalleAsistenciaInline]


@admin.register(DetalleAsistencia)
class DetalleAsistenciaAdmin(admin.ModelAdmin):
    list_display = ('registro', 'estudiante', 'estado', 'observacion')
    list_filter = ('estado',)

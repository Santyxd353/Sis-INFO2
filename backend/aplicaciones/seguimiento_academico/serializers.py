from rest_framework import serializers

from .models import HistorialEstudiante, Nota, RiesgoAcademico, ConfiguracionRiesgo


class NotaSerializer(serializers.ModelSerializer):
    materia_nombre = serializers.CharField(source='materia.nombre', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_evaluacion_display', read_only=True)

    class Meta:
        model = Nota
        fields = [
            'id', 'historial', 'materia', 'materia_nombre', 'tipo_evaluacion',
            'tipo_display', 'nota', 'ponderacion',
        ]


class HistorialEstudianteSerializer(serializers.ModelSerializer):
    notas = NotaSerializer(many=True, read_only=True)
    estudiante_nombre = serializers.CharField(source='estudiante.usuario.nombre', read_only=True)
    estudiante_apellido = serializers.CharField(source='estudiante.usuario.apellido', read_only=True)
    curso_nombre = serializers.CharField(source='curso.nombre', read_only=True)
    gestion = serializers.IntegerField(source='periodo.calendario.año', read_only=True)
    periodo_nombre = serializers.CharField(source='periodo.nombre', read_only=True)

    class Meta:
        model = HistorialEstudiante
        fields = [
            'id', 'estudiante', 'estudiante_nombre', 'estudiante_apellido',
            'periodo', 'periodo_nombre', 'gestion', 'curso', 'curso_nombre',
            'promedio', 'observaciones', 'notas', 'fecha_registro',
        ]


class RiesgoAcademicoSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(source='estudiante.usuario.nombre', read_only=True)
    estudiante_apellido = serializers.CharField(source='estudiante.usuario.apellido', read_only=True)
    responsable_nombre = serializers.CharField(source='responsable.nombre', read_only=True)
    nivel_display = serializers.CharField(source='get_nivel_display', read_only=True)

    class Meta:
        model = RiesgoAcademico
        fields = [
            'id', 'estudiante', 'estudiante_nombre', 'estudiante_apellido',
            'periodo', 'nivel', 'nivel_display', 'motivo', 'acciones_propuestas',
            'responsable', 'responsable_nombre', 'activo', 'fecha_evaluacion',
            'fecha_actualizacion',
        ]
        read_only_fields = ['responsable', 'fecha_evaluacion', 'fecha_actualizacion']


class ConfiguracionRiesgoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionRiesgo
        fields = '__all__'


class AlertaSerializer(serializers.Serializer):
    """Resultado del análisis de riesgo de un estudiante."""
    estudiante = serializers.IntegerField()
    nombre = serializers.CharField()
    apellido = serializers.CharField()
    curso = serializers.CharField(allow_null=True)
    promedio = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    porcentaje_faltas = serializers.DecimalField(max_digits=5, decimal_places=2)
    nivel = serializers.CharField(allow_null=True)
    nivel_display = serializers.CharField(allow_null=True)
    tipos = serializers.ListField(child=serializers.CharField())
    motivos = serializers.ListField(child=serializers.CharField())
    umbral_rendimiento = serializers.DecimalField(max_digits=5, decimal_places=2)
    umbral_inasistencia = serializers.DecimalField(max_digits=5, decimal_places=2)

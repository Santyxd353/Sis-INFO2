from rest_framework import serializers

from aplicaciones.academico.models import MateriaCurso
from aplicaciones.calendario.models import Periodo
from aplicaciones.estudiantes.models import Estudiante
from .models import RegistroAsistencia, DetalleAsistencia


class DetalleAsistenciaSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(source='estudiante.usuario.nombre', read_only=True)
    estudiante_apellido = serializers.CharField(source='estudiante.usuario.apellido', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = DetalleAsistencia
        fields = [
            'id', 'registro', 'estudiante', 'estudiante_nombre',
            'estudiante_apellido', 'estado', 'estado_display', 'observacion',
        ]


class RegistroAsistenciaSerializer(serializers.ModelSerializer):
    detalles = DetalleAsistenciaSerializer(many=True, read_only=True)
    curso = serializers.IntegerField(source='asignacion.curso_id', read_only=True)
    curso_nombre = serializers.CharField(source='asignacion.curso.nombre', read_only=True)
    materia = serializers.IntegerField(source='asignacion.materia_id', read_only=True)
    materia_nombre = serializers.CharField(source='asignacion.materia.nombre', read_only=True)
    asignacion_display = serializers.CharField(source='asignacion', read_only=True)
    docente_nombre = serializers.CharField(source='docente.nombre', read_only=True)

    class Meta:
        model = RegistroAsistencia
        fields = [
            'id', 'fecha', 'asignacion', 'asignacion_display', 'curso', 'curso_nombre',
            'materia', 'materia_nombre', 'periodo', 'observacion', 'docente',
            'docente_nombre', 'detalles', 'creado', 'actualizado',
        ]
        read_only_fields = ['docente', 'creado', 'actualizado']


class _DetalleInputSerializer(serializers.Serializer):
    estudiante = serializers.PrimaryKeyRelatedField(queryset=Estudiante.objects.all())
    estado = serializers.ChoiceField(choices=DetalleAsistencia.ESTADOS)
    observacion = serializers.CharField(required=False, allow_blank=True, default='')


class RegistrarAsistenciaSerializer(serializers.Serializer):
    """Registra/actualiza la asistencia completa de una asignación en una fecha."""
    asignacion = serializers.PrimaryKeyRelatedField(queryset=MateriaCurso.objects.all())
    fecha = serializers.DateField()
    periodo = serializers.PrimaryKeyRelatedField(
        queryset=Periodo.objects.all(), required=False, allow_null=True,
    )
    observacion = serializers.CharField(required=False, allow_blank=True, default='')
    detalles = _DetalleInputSerializer(many=True)

    def validate_detalles(self, value):
        ids = [d['estudiante'].pk for d in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                'No se puede registrar dos veces al mismo estudiante en la misma fecha y asignación.'
            )
        return value


class EstudianteAsistenciaSerializer(serializers.Serializer):
    """Fila de la lista de estudiantes para registrar asistencia."""
    estudiante = serializers.IntegerField()
    nombre = serializers.CharField()
    apellido = serializers.CharField()
    rude = serializers.CharField(allow_blank=True, allow_null=True)
    estado = serializers.CharField(allow_null=True)
    observacion = serializers.CharField(allow_blank=True)


class ResumenAsistenciaSerializer(serializers.Serializer):
    estudiante = serializers.IntegerField()
    nombre = serializers.CharField()
    apellido = serializers.CharField()
    curso = serializers.CharField(allow_null=True)
    total = serializers.IntegerField()
    presentes = serializers.IntegerField()
    ausentes = serializers.IntegerField()
    tardes = serializers.IntegerField()
    licencias = serializers.IntegerField()
    porcentaje_asistencia = serializers.DecimalField(max_digits=5, decimal_places=2)
    porcentaje_faltas = serializers.DecimalField(max_digits=5, decimal_places=2)

from rest_framework import serializers

from aplicaciones.usuarios.tenancy import validar_unidad
from .models import Aviso, Comunicado
from .seguridad import exigir_gestor, puede_gestionar, usuarios_unidad


class ComunicadoSerializer(serializers.ModelSerializer):
    leido_at = serializers.SerializerMethodField()
    puede_gestionar = serializers.SerializerMethodField()
    es_destinatario = serializers.SerializerMethodField()
    estadisticas = serializers.SerializerMethodField()

    class Meta:
        model = Comunicado
        fields = ['id', 'titulo', 'cuerpo', 'unidad_educativa', 'curso', 'prioridad',
                  'requiere_confirmacion', 'estado', 'created_at', 'publicado_at',
                  'leido_at', 'puede_gestionar', 'es_destinatario', 'estadisticas']
        read_only_fields = ['estado', 'created_at', 'publicado_at']
        extra_kwargs = {'cuerpo': {'max_length': 20000}}

    def validate(self, attrs):
        unit = attrs.get('unidad_educativa', getattr(self.instance, 'unidad_educativa', None))
        exigir_gestor(self.context['request'].user, unit)
        course = attrs.get('curso', getattr(self.instance, 'curso', None))
        if course and course.paralelo.grado.unidad_educativa_id != unit.pk:
            raise serializers.ValidationError({'curso': 'El curso no pertenece a la unidad educativa.'})
        return attrs

    def get_leido_at(self, obj):
        value = obj.destinatarios.filter(usuario=self.context['request'].user).values_list('leido_at', flat=True).first()
        return serializers.DateTimeField().to_representation(value) if value else None

    def get_puede_gestionar(self, obj):
        user = self.context['request'].user
        if not puede_gestionar(user):
            return False
        validar_unidad(user, obj.unidad_educativa)
        return True

    def get_es_destinatario(self, obj):
        user = self.context['request'].user
        return (obj.estado in (Comunicado.Estado.PUBLICADO, Comunicado.Estado.ARCHIVADO)
                and usuarios_unidad(obj.unidad_educativa_id).filter(pk=user.pk).exists()
                and obj.destinatarios.filter(usuario_id=user.pk).exists())

    def get_estadisticas(self, obj):
        if not self.get_puede_gestionar(obj):
            return None
        total = obj.destinatarios.count()
        read = obj.destinatarios.filter(leido_at__isnull=False).count()
        return {'destinatarios': total, 'leidos': read, 'porcentaje_lectura': round(read * 100 / total, 2) if total else 0.0}


class AvisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aviso
        fields = ['id', 'tipo', 'titulo', 'cuerpo', 'created_at', 'leida_at', 'comunicado', 'datos']
        read_only_fields = fields


class AlertaSerializer(serializers.Serializer):
    estudiante = serializers.IntegerField(min_value=1)
    tipo = serializers.ChoiceField(choices=['PAGO', 'CONTINGENCIA'])
    titulo = serializers.CharField(max_length=200)
    cuerpo = serializers.CharField(max_length=20000)
    clave_evento = serializers.CharField(max_length=120)

from rest_framework import serializers

from .models import CalendarioAcademico, Feriado, Periodo, TipoFeriado


class CalendarioAcademicoSerializer(serializers.ModelSerializer):
    unidad_nombre = serializers.CharField(source='unidad_educativa.nombre', read_only=True)

    class Meta:
        model = CalendarioAcademico
        fields = '__all__'


class PeriodoSerializer(serializers.ModelSerializer):
    calendario_nombre = serializers.SerializerMethodField()

    def get_calendario_nombre(self, obj):
        return str(obj.calendario)

    class Meta:
        model = Periodo
        fields = '__all__'


class TipoFeriadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoFeriado
        fields = '__all__'


class FeriadoSerializer(serializers.ModelSerializer):
    calendario_nombre = serializers.SerializerMethodField()
    tipo_nombre = serializers.CharField(source='tipo.nombre', read_only=True)

    def get_calendario_nombre(self, obj):
        return str(obj.calendario)

    class Meta:
        model = Feriado
        fields = '__all__'

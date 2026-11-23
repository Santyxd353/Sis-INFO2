from rest_framework import serializers

from .models import Aula, Colegio, Modulo, UnidadEducativa


class ColegioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Colegio
        fields = ['id', 'nombre', 'direccion', 'telefono', 'email', 'sitio_web']


class UnidadEducativaSerializer(serializers.ModelSerializer):
    colegio = ColegioSerializer(read_only=True)
    colegio_id = serializers.PrimaryKeyRelatedField(
        queryset=Colegio.objects.all(), source='colegio', required=False, allow_null=True,
    )

    class Meta:
        model = UnidadEducativa
        fields = [
            'id',
            'codigo_sie',
            'turno',
            'nombre',
            'direccion',
            'telefono',
            'nivel',
            'colegio',
            'colegio_id',
        ]


class ModuloSerializer(serializers.ModelSerializer):
    colegio_id = serializers.IntegerField(source='colegio_fk_id', read_only=True)

    class Meta:
        model = Modulo
        fields = [
            'id', 'nombre', 'cantidad_aulas', 'descripcion', 'pisos',
            'unidad_educativa', 'colegio_id', 'estado', 'created_at', 'updated_at',
        ]
        read_only_fields = ['estado', 'created_at', 'updated_at']

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('No puede estar vacío.')
        return value

    def validate(self, attrs):
        unit = attrs.get('unidad_educativa', getattr(self.instance, 'unidad_educativa', None))
        name = attrs.get('nombre', getattr(self.instance, 'nombre', '')).strip()
        if unit is None:
            raise serializers.ValidationError({'unidad_educativa': 'Es obligatoria para infraestructura nueva.'})
        duplicate = Modulo.objects.filter(
            unidad_educativa=unit, estado=Modulo.Estado.ACTIVO, eliminado_at__isnull=True,
            nombre__iexact=name,
        )
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({'nombre': 'Ya existe un módulo activo con ese nombre en la unidad.'})
        return attrs


class AulaSerializer(serializers.ModelSerializer):
    unidad_educativa_id = serializers.IntegerField(source='modulo.unidad_educativa_id', read_only=True)
    colegio_id = serializers.IntegerField(source='modulo.unidad_educativa.colegio_id', read_only=True)

    class Meta:
        model = Aula
        fields = [
            'id', 'modulo', 'nombre', 'capacidad', 'estado', 'tipo', 'equipamiento', 'piso',
            'unidad_educativa_id', 'colegio_id', 'created_at', 'updated_at',
        ]
        read_only_fields = ['estado', 'created_at', 'updated_at']

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('No puede estar vacío.')
        return value

    def validate(self, attrs):
        module = attrs.get('modulo', getattr(self.instance, 'modulo', None))
        name = attrs.get('nombre', getattr(self.instance, 'nombre', '')).strip()
        if module is None:
            raise serializers.ValidationError({'modulo': 'Es obligatorio.'})
        if (module.estado != Modulo.Estado.ACTIVO or module.eliminado_at is not None
                or module.unidad_educativa_id is None):
            raise serializers.ValidationError({'modulo': 'Seleccione un módulo activo y conciliado con una unidad educativa.'})
        duplicate = Aula.objects.filter(modulo=module, estado=True, eliminado_at__isnull=True, nombre__iexact=name)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({'nombre': 'Ya existe un aula activa con ese nombre en el módulo.'})
        return attrs

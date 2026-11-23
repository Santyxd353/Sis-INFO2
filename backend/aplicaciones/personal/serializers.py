from rest_framework import serializers

from aplicaciones.usuarios.serializer import UsuarioSerializer
from aplicaciones.usuarios.models import Rol, Usuario
from aplicaciones.academico.models import Curso
from aplicaciones.institucion.models import UnidadEducativa

from .models import Profesor


class ProfesorSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='usuario_id', read_only=True)
    usuario = UsuarioSerializer(read_only=True)
    unidad_nombre = serializers.CharField(source='unidad.nombre', read_only=True)
    usuario_id = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all(), source='usuario')
    unidad_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadEducativa.objects.all(), source='unidad', required=False, allow_null=True,
    )

    class Meta:
        model = Profesor
        fields = ['id', 'usuario', 'usuario_id', 'estado', 'unidad', 'unidad_id', 'unidad_nombre']
        read_only_fields = ['unidad']

    def validate(self, attrs):
        from aplicaciones.usuarios.tenancy import validar_unidad

        usuario = attrs.get('usuario', getattr(self.instance, 'usuario', None))
        unidad = attrs.get('unidad', getattr(self.instance, 'unidad', None))
        if usuario and unidad and usuario.unidad_id not in (None, unidad.pk):
            raise serializers.ValidationError({'usuario_id': 'El usuario pertenece a otra unidad educativa.'})
        request = self.context.get('request')
        if request:
            if not unidad:
                raise serializers.ValidationError({'unidad_id': 'La unidad educativa es obligatoria.'})
            try:
                validar_unidad(request.user, unidad)
            except Exception as exc:
                raise serializers.ValidationError({'unidad_id': str(exc.detail)})
            if not usuario or usuario.unidad_id != unidad.pk:
                raise serializers.ValidationError({'usuario_id': 'El usuario pertenece a otra unidad educativa.'})
        return attrs


class GestionProfesorSerializer(serializers.Serializer):
    """Crea y edita la cuenta docente y su perfil en una sola operación."""

    id = serializers.IntegerField(source='usuario_id', read_only=True)
    ci = serializers.CharField(max_length=20)
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    username = serializers.CharField(max_length=50)
    email = serializers.EmailField(max_length=100)
    password = serializers.CharField(
        write_only=True, required=False, min_length=8, trim_whitespace=False,
    )
    sexo = serializers.ChoiceField(choices=('M', 'F'))
    fecha_nacimiento = serializers.DateField(required=False, allow_null=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    unidad_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadEducativa.objects.all(), source='unidad'
    )
    curso_ids = serializers.PrimaryKeyRelatedField(
        queryset=Curso.objects.select_related('paralelo__grado').all(),
        many=True,
        required=False,
        allow_empty=True,
    )
    estado = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({
                'password': 'La contraseña temporal es obligatoria.'
            })
        unidad = attrs.get('unidad', getattr(self.instance, 'unidad', None))
        cursos = attrs.get('curso_ids')
        if cursos is not None and unidad:
            if any(
                curso.paralelo.grado.unidad_educativa_id != unidad.pk
                for curso in cursos
            ):
                raise serializers.ValidationError({
                    'curso_ids': 'Todos los cursos deben pertenecer a la unidad educativa.'
                })
        return attrs

    def _datos_usuario(self, validated_data, *, incluir_rol=False):
        datos = {}
        for campo in (
            'ci', 'nombre', 'apellido', 'username', 'email', 'password',
            'sexo', 'fecha_nacimiento', 'telefono',
        ):
            if campo in validated_data:
                datos[campo] = validated_data[campo]
        if 'unidad' in validated_data:
            datos['unidad_id'] = validated_data['unidad'].pk
        if 'curso_ids' in validated_data:
            datos['curso_ids'] = [curso.pk for curso in validated_data['curso_ids']]
        if incluir_rol:
            rol, _ = Rol.objects.get_or_create(
                nombre='Profesor', defaults={'descripcion': 'Personal docente'}
            )
            datos['rol_id'] = rol.pk
        return datos

    def create(self, validated_data):
        from django.db import transaction

        estado = validated_data.pop('estado', True)
        datos_usuario = self._datos_usuario(validated_data, incluir_rol=True)
        with transaction.atomic():
            usuario_serializer = UsuarioSerializer(
                data=datos_usuario, context=self.context
            )
            usuario_serializer.is_valid(raise_exception=True)
            usuario = usuario_serializer.save()
            profesor = usuario.profesor
            profesor.estado = estado
            profesor.save(update_fields=['estado'])
        return profesor

    def update(self, instance, validated_data):
        from django.db import transaction

        estado = validated_data.pop('estado', None)
        datos_usuario = self._datos_usuario(validated_data)
        with transaction.atomic():
            if datos_usuario:
                usuario_serializer = UsuarioSerializer(
                    instance.usuario,
                    data=datos_usuario,
                    partial=True,
                    context=self.context,
                )
                usuario_serializer.is_valid(raise_exception=True)
                usuario_serializer.save()
            if estado is not None:
                instance.estado = estado
                instance.save(update_fields=['estado'])
        return instance

    def to_representation(self, instance):
        return ProfesorSerializer(instance, context=self.context).data

# aplicaciones/personal/serializers.py
from rest_framework import serializers
from aplicaciones.usuarios.models import Usuario
from aplicaciones.academico.models import Curso
from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from .models import DocumentoAcademicoEmitido, Estudiante, Tutor, TutorEstudiante, HistorialInscripcion
from aplicaciones.institucion.models import UnidadEducativa

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'ci', 'nombre', 'apellido', 'sexo', 'email', 'fecha_nacimiento', 'username']

class CursoSimpleSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='pk', read_only=True)

    class Meta:
        model = Curso
        fields = ['id', 'paralelo_id', 'nombre']

class UnidadEducativaSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadEducativa
        fields = ['id', 'nombre']        
# --- Estudiante ---
class EstudianteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='usuario.id', read_only=True) 
    usuario   = UsuarioSerializer(read_only=True)
    curso     = CursoSimpleSerializer(read_only=True)
    unidad = UnidadEducativaSimpleSerializer(read_only=True)   
    class Meta:
        model  = Estudiante
        fields = ['id','usuario', 'rude', 'estado', 'curso', 'unidad']

class CreateEstudianteSerializer(serializers.ModelSerializer):
    usuario_id = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.all(),
        source='usuario',
        write_only=True
    )
    curso_id = serializers.PrimaryKeyRelatedField(
        queryset=Curso.objects.all(),
        source='curso',
        allow_null=True,
        required=False,
        write_only=True
    )
    unidad_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadEducativa.objects.all(),
        source='unidad',
        allow_null=True,
        required=False,
        write_only=True
    )

    class Meta:
        model  = Estudiante
        fields = ['usuario_id', 'rude', 'estado', 'curso_id', 'unidad_id']

    def validate(self, attrs):
        from aplicaciones.usuarios.tenancy import validar_unidad

        unidad = attrs.get('unidad', getattr(self.instance, 'unidad', None))
        curso = attrs.get('curso', getattr(self.instance, 'curso', None))
        usuario = attrs.get('usuario', getattr(self.instance, 'usuario', None))
        if not unidad:
            raise serializers.ValidationError({'unidad_id': 'La unidad educativa es obligatoria.'})
        if not curso:
            raise serializers.ValidationError({'curso_id': 'El curso es obligatorio.'})
        if curso.paralelo.grado.unidad_educativa_id != unidad.pk:
            raise serializers.ValidationError({'curso_id': 'El curso no pertenece a la unidad educativa.'})
        if usuario and usuario.unidad_id not in (None, unidad.pk):
            raise serializers.ValidationError({'usuario_id': 'El usuario pertenece a otra unidad educativa.'})

        request = self.context.get('request')
        if request:
            try:
                validar_unidad(request.user, unidad)
            except Exception as exc:
                raise serializers.ValidationError({'unidad_id': str(exc.detail)})
        return attrs

# --- Tutor ---
class TutorSerializer(serializers.ModelSerializer):
    usuario     = UsuarioSerializer(read_only=True)
    parentesco_display = serializers.CharField(source='get_parentesco_display', read_only=True)

    class Meta:
        model  = Tutor
        fields = ['usuario', 'parentesco', 'parentesco_display']

class CreateTutorSerializer(serializers.ModelSerializer):
    usuario_id = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.all(),
        source='usuario',
        write_only=True
    )

    class Meta:
        model  = Tutor
        fields = ['usuario_id', 'parentesco']

    def validate(self, attrs):
        from aplicaciones.usuarios.tenancy import validar_unidad

        usuario = attrs.get('usuario', getattr(self.instance, 'usuario', None))
        request = self.context.get('request')
        if request:
            if not usuario or not usuario.unidad:
                raise serializers.ValidationError({'usuario_id': 'El usuario no tiene unidad educativa.'})
            try:
                validar_unidad(request.user, usuario.unidad)
            except Exception as exc:
                raise serializers.ValidationError({'usuario_id': str(exc.detail)})
        return attrs

# --- TutorEstudiante ---
class TutorEstudianteSerializer(serializers.ModelSerializer):
    tutor      = TutorSerializer(read_only=True)
    estudiante = EstudianteSerializer(read_only=True)

    class Meta:
        model  = TutorEstudiante
        fields = ['id', 'tutor', 'estudiante', 'fecha_asignacion', 'es_principal']

class CreateTutorEstudianteSerializer(serializers.ModelSerializer):
    tutor_id      = serializers.PrimaryKeyRelatedField(
        queryset=Tutor.objects.all(),
        source='tutor',
        write_only=True
    )
    estudiante_id = serializers.PrimaryKeyRelatedField(
        queryset=Estudiante.objects.all(),
        source='estudiante',
        write_only=True
    )

    class Meta:
        model  = TutorEstudiante
        fields = ['tutor_id', 'estudiante_id', 'es_principal']

    def validate(self, attrs):
        from aplicaciones.usuarios.tenancy import validar_unidad

        tutor = attrs.get('tutor', getattr(self.instance, 'tutor', None))
        estudiante = attrs.get('estudiante', getattr(self.instance, 'estudiante', None))
        unidad_tutor = tutor.usuario.unidad_id if tutor else None
        unidad_estudiante = estudiante.unidad_id if estudiante else None
        if not unidad_tutor or unidad_tutor != unidad_estudiante:
            raise serializers.ValidationError(
                'El tutor y el estudiante deben pertenecer a la misma unidad educativa.'
            )
        request = self.context.get('request')
        if request:
            try:
                validar_unidad(request.user, estudiante.unidad)
            except Exception as exc:
                raise serializers.ValidationError(str(exc.detail))
        return attrs


# --- Historial de Inscripción ---
class HistorialInscripcionSerializer(serializers.ModelSerializer):
    estudiante = EstudianteSerializer(read_only=True)
    curso_anterior = CursoSimpleSerializer(read_only=True)
    curso_nuevo = CursoSimpleSerializer(read_only=True)
    unidad = UnidadEducativaSimpleSerializer(read_only=True)
    usuario_registra = UsuarioSerializer(read_only=True)
    tipo_movimiento_display = serializers.CharField(source='get_tipo_movimiento_display', read_only=True)
    
    class Meta:
        model = HistorialInscripcion
        fields = [
            'id', 'estudiante', 'curso_anterior', 'curso_nuevo', 'unidad',
            'tipo_movimiento', 'tipo_movimiento_display', 'fecha_inscripcion',
            'usuario_registra', 'observaciones'
        ]


class NuevoEstudianteInscripcionSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    ci = serializers.CharField(max_length=20)
    email = serializers.EmailField(max_length=100)
    sexo = serializers.ChoiceField(choices=('M', 'F'))
    username = serializers.CharField(max_length=50)
    password = serializers.CharField(min_length=8, write_only=True, trim_whitespace=False)

    def validate_username(self, value):
        if value and Usuario.objects.filter(username__iexact=value.strip()).exists():
            raise serializers.ValidationError('Este nombre de usuario ya está registrado.')
        return value.strip()


# --- Inscripción (Crear nueva) ---
class InscripcionSerializer(serializers.Serializer):
    """Serializer para validar y crear/actualizar inscripción de estudiante"""
    
    estudiante_id = serializers.IntegerField(required=False, allow_null=True)
    usuario_id = serializers.IntegerField(required=False, allow_null=True)
    nuevo_estudiante = NuevoEstudianteInscripcionSerializer(required=False, allow_null=True)
    curso_id = serializers.IntegerField(required=True)
    unidad_id = serializers.IntegerField(required=True)
    rude = serializers.CharField(required=True, max_length=50)
    observaciones = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    def validate(self, data):
        """Validaciones de negocio para inscripción"""
        curso_id = data.get('curso_id', getattr(self.instance, 'curso_id', None))
        unidad_id = data.get('unidad_id', getattr(self.instance, 'unidad_id', None))
        estudiante_id = data.get('estudiante_id')
        usuario_id = data.get('usuario_id')
        nuevo_estudiante = data.get('nuevo_estudiante')
        
        # Debe ser crear nuevo o actualizar existente
        if not self.instance and not estudiante_id and not usuario_id and not nuevo_estudiante:
            raise serializers.ValidationError(
                "Seleccione un estudiante existente o complete los datos del nuevo estudiante."
            )

        if nuevo_estudiante:
            if Usuario.objects.filter(ci=nuevo_estudiante['ci'].strip()).exists():
                raise serializers.ValidationError({
                    'nuevo_estudiante': 'Ya existe una persona registrada con ese CI.'
                })
            if Usuario.objects.filter(email__iexact=nuevo_estudiante['email'].strip()).exists():
                raise serializers.ValidationError({
                    'nuevo_estudiante': 'Ya existe una persona registrada con ese correo electrónico.'
                })
        
        try:
            unidad = UnidadEducativa.objects.get(id=unidad_id)
        except UnidadEducativa.DoesNotExist:
            raise serializers.ValidationError({'unidad_id': 'La unidad educativa no existe.'})

        # El identificador recibido corresponde al curso, no al paralelo.
        try:
            curso = Curso.objects.select_related('paralelo__grado').get(pk=curso_id)
        except Curso.DoesNotExist:
            raise serializers.ValidationError({'curso_id': 'El curso no existe.'})
        if curso.paralelo.grado.unidad_educativa_id != unidad.pk:
            raise serializers.ValidationError({'curso_id': 'El curso no pertenece a la unidad educativa.'})

        from aplicaciones.usuarios.tenancy import validar_unidad
        request = self.context.get('request')
        if request:
            try:
                validar_unidad(request.user, unidad)
            except Exception as exc:
                raise serializers.ValidationError({'unidad_id': str(exc.detail)})
        
        # Si es estudiante existente, validar que no esté duplicado en el mismo curso
        if estudiante_id:
            try:
                estudiante = Estudiante.objects.get(usuario_id=estudiante_id)
                if estudiante.unidad_id != unidad.pk:
                    raise serializers.ValidationError('El estudiante pertenece a otra unidad educativa.')
                if estudiante.curso_id == curso_id:
                    raise serializers.ValidationError(
                        "El estudiante ya está inscrito en este curso"
                    )
            except Estudiante.DoesNotExist:
                raise serializers.ValidationError(f"Estudiante con ID {estudiante_id} no existe")
        
        # Si es nuevo usuario, verificar que no exista como estudiante
        if usuario_id:
            try:
                usuario = Usuario.objects.get(id=usuario_id)
                if usuario.unidad_id != unidad.pk:
                    raise serializers.ValidationError('El usuario pertenece a otra unidad educativa.')
                if hasattr(usuario, 'estudiante'):
                    raise serializers.ValidationError(
                        "Este usuario ya es estudiante. Use estudiante_id para cambiar de curso"
                    )
            except Usuario.DoesNotExist:
                raise serializers.ValidationError(f"Usuario con ID {usuario_id} no existe")
        
        # Validar RUDE único
        rude = data.get('rude', getattr(self.instance, 'rude', None))
        if self.instance:
            estudiante_existente = Estudiante.objects.exclude(
                usuario_id=self.instance.usuario_id,
            ).filter(rude=rude).first()
        elif estudiante_id:
            estudiante_existente = Estudiante.objects.exclude(usuario_id=estudiante_id).filter(rude=rude).first()
        else:
            estudiante_existente = Estudiante.objects.filter(rude=rude).first()
        
        if estudiante_existente:
            raise serializers.ValidationError(f"RUDE {rude} ya está registrado")
        
        data['curso'] = curso
        data['unidad'] = unidad
        return data
    
    def create(self, validated_data):
        """Crear nueva inscripción"""
        curso = validated_data.pop('curso')
        validated_data.pop('unidad_id')
        unidad = validated_data.pop('unidad')
        observaciones = validated_data.pop('observaciones', '')
        usuario_id = validated_data.pop('usuario_id', None)
        nuevo_estudiante = validated_data.pop('nuevo_estudiante', None)
        
        # Crear automáticamente la cuenta cuando los datos llegan desde la inscripción.
        if nuevo_estudiante:
            from aplicaciones.usuarios.models import Rol

            rol, _ = Rol.objects.get_or_create(
                nombre='Estudiante',
                defaults={'descripcion': 'Estudiante de la unidad educativa'},
            )
            username = nuevo_estudiante['username'].strip()

            usuario = Usuario.objects.create_user(
                ci=nuevo_estudiante['ci'].strip(),
                email=nuevo_estudiante['email'].strip(),
                nombre=nuevo_estudiante['nombre'].strip(),
                apellido=nuevo_estudiante['apellido'].strip(),
                password=nuevo_estudiante['password'],
                username=username,
                sexo=nuevo_estudiante['sexo'],
                rol=rol,
                unidad=unidad,
            )
        else:
            usuario = Usuario.objects.get(id=usuario_id)
        estudiante = Estudiante.objects.create(
            usuario=usuario,
            curso=curso,
            unidad=unidad,
            rude=validated_data['rude'],
            estado=True
        )
        
        # Registrar historial
        HistorialInscripcion.objects.create(
            estudiante=estudiante,
            curso_nuevo=curso,
            unidad=unidad,
            tipo_movimiento='NUEVA',
            usuario_registra=self.context['request'].user,
            observaciones=observaciones
        )
        
        return estudiante
    
    def update(self, instance, validated_data):
        """Actualizar inscripción (cambio de curso)"""
        from aplicaciones.usuarios.utils import get_client_ip, registrar_bitacora
        
        curso = validated_data.pop('curso')
        validated_data.pop('unidad_id')
        unidad = validated_data.pop('unidad')
        observaciones = validated_data.pop('observaciones', '')
        rude = validated_data.get('rude', instance.rude)
        
        curso_anterior = instance.curso
        instance.curso = curso
        instance.unidad = unidad
        instance.rude = rude
        instance.save()
        if instance.usuario.unidad_id != unidad.pk:
            instance.usuario.unidad = unidad
            instance.usuario.save(update_fields=['unidad'])
        
        # Registrar historial
        HistorialInscripcion.objects.create(
            estudiante=instance,
            curso_anterior=curso_anterior,
            curso_nuevo=curso,
            unidad=unidad,
            tipo_movimiento='CAMBIO',
            usuario_registra=self.context['request'].user,
            observaciones=observaciones
        )
        
        registrar_bitacora(
            usuario=self.context['request'].user,
            ip=get_client_ip(self.context['request']),
            tabla_afectada='estudiante_inscripcion',
            accion='cambio_curso',
            descripcion=f'Cambio de curso: {curso_anterior} → {curso}'
        )

        return instance


# === HU-19: Centralizadores y Boletines ===

class DocumentoAcademicoEmitidoSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(
        source='historial_inscripcion.estudiante.usuario.get_full_name', read_only=True, default=None,
    )
    curso_nombre = serializers.CharField(source='curso.nombre', read_only=True, default=None)
    periodo_nombre = serializers.CharField(source='periodo.nombre', read_only=True, default=None)
    gestion_anio = serializers.IntegerField(source='calendario_academico.año', read_only=True)
    descarga_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoAcademicoEmitido
        fields = [
            'id', 'tipo', 'historial_inscripcion', 'estudiante_nombre', 'curso', 'curso_nombre',
            'periodo', 'periodo_nombre', 'calendario_academico', 'gestion_anio', 'version',
            'archivo_mime', 'archivo_tamano', 'emisor_snapshot', 'emitido_at', 'descarga_url',
        ]
        read_only_fields = fields

    def get_descarga_url(self, obj):
        return f'/api/estudiantes/documentos-academicos/{obj.pk}/descargar/'


class GenerarBoletinSerializer(serializers.Serializer):
    historial_inscripcion = serializers.PrimaryKeyRelatedField(
        queryset=HistorialInscripcion.objects.all(),
    )
    calendario_academico = serializers.PrimaryKeyRelatedField(
        queryset=CalendarioAcademico.objects.all(),
    )
    periodo = serializers.PrimaryKeyRelatedField(
        queryset=Periodo.objects.all(), required=False, allow_null=True,
    )

    def validate(self, attrs):
        periodo = attrs.get('periodo')
        calendario = attrs['calendario_academico']
        historial = attrs['historial_inscripcion']
        if periodo and periodo.calendario_id != calendario.pk:
            raise serializers.ValidationError(
                {'periodo': 'No corresponde a la gestión académica indicada.'},
            )
        if historial.unidad_id != calendario.unidad_educativa_id:
            raise serializers.ValidationError(
                {'calendario_academico': 'No corresponde a la unidad educativa del estudiante.'},
            )
        return attrs


class GenerarCentralizadorSerializer(serializers.Serializer):
    curso = serializers.PrimaryKeyRelatedField(queryset=Curso.objects.all())
    calendario_academico = serializers.PrimaryKeyRelatedField(
        queryset=CalendarioAcademico.objects.all(),
    )
    periodo = serializers.PrimaryKeyRelatedField(
        queryset=Periodo.objects.all(), required=False, allow_null=True,
    )

    def validate(self, attrs):
        periodo = attrs.get('periodo')
        calendario = attrs['calendario_academico']
        curso = attrs['curso']
        if periodo and periodo.calendario_id != calendario.pk:
            raise serializers.ValidationError(
                {'periodo': 'No corresponde a la gestión académica indicada.'},
            )
        if curso.paralelo.grado.unidad_educativa_id != calendario.unidad_educativa_id:
            raise serializers.ValidationError(
                {'calendario_academico': 'No corresponde a la unidad educativa del curso.'},
            )
        return attrs

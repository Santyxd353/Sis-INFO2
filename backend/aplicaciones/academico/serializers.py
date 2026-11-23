from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from aplicaciones.calendario.models import CalendarioAcademico
from aplicaciones.estudiantes.models import HistorialInscripcion

from .models import (
    ActividadEvaluacion, AsignacionDocente, Calificacion,
    ConfiguracionEvaluacion, Curso, DimensionEvaluacion, Grado, Materia, MateriaCurso,
    Paralelo,
)


class GradoSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(read_only=True)
    nivel_educativo_display = serializers.CharField(
        source='get_nivel_educativo_display',
        read_only=True,
    )
    unidad_nombre = serializers.CharField(source='unidad_educativa.nombre', read_only=True)

    class Meta:
        model = Grado
        fields = [
            'id',
            'unidad_educativa',
            'unidad_nombre',
            'nivel_educativo',
            'nivel_educativo_display',
            'numero',
            'nombre',
        ]


class ParaleloSerializer(serializers.ModelSerializer):
    grado = GradoSerializer(read_only=True)
    grado_id = serializers.PrimaryKeyRelatedField(queryset=Grado.objects.all(), source='grado')

    class Meta:
        model = Paralelo
        fields = ['id', 'grado', 'grado_id', 'letra']


class CursoSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='pk', read_only=True)
    paralelo = ParaleloSerializer(read_only=True)
    paralelo_id = serializers.PrimaryKeyRelatedField(queryset=Paralelo.objects.all(), source='paralelo')
    tutor_nombre = serializers.SerializerMethodField()

    def get_tutor_nombre(self, obj):
        return str(obj.tutor.usuario) if obj.tutor else None

    class Meta:
        model = Curso
        fields = ['id', 'paralelo', 'paralelo_id', 'nombre', 'tutor', 'tutor_nombre']


class AsignacionDocenteSerializer(serializers.ModelSerializer):
    profesor_nombre = serializers.CharField(source='profesor.usuario.get_full_name', read_only=True)
    curso_nombre = serializers.CharField(source='curso.nombre', read_only=True)
    materia_nombre = serializers.CharField(source='materia_curso.materia.nombre', read_only=True)
    gestion_anio = serializers.IntegerField(source='calendario_academico.año', read_only=True)
    unidad_educativa = serializers.IntegerField(
        source='curso.paralelo.grado.unidad_educativa_id', read_only=True,
    )
    unidad_nombre = serializers.CharField(
        source='curso.paralelo.grado.unidad_educativa.nombre', read_only=True,
    )
    nivel_educativo = serializers.CharField(
        source='curso.paralelo.grado.nivel_educativo', read_only=True,
    )

    class Meta:
        model = AsignacionDocente
        fields = [
            'id', 'tipo', 'calendario_academico', 'gestion_anio',
            'curso', 'curso_nombre', 'materia_curso', 'materia_nombre',
            'profesor', 'profesor_nombre', 'unidad_educativa', 'unidad_nombre',
            'nivel_educativo', 'fecha_inicio', 'fecha_fin', 'horas_semanales',
            'estado', 'created_at', 'updated_at', 'eliminado_at',
        ]
        read_only_fields = ['estado', 'created_at', 'updated_at', 'eliminado_at']

    def validate(self, attrs):
        instance = self.instance
        calendario = attrs.get('calendario_academico', getattr(instance, 'calendario_academico', None))
        curso = attrs.get('curso', getattr(instance, 'curso', None))
        profesor = attrs.get('profesor', getattr(instance, 'profesor', None))
        materia_curso = attrs.get('materia_curso', getattr(instance, 'materia_curso', None))

        if instance is None and calendario is None:
            raise serializers.ValidationError({
                'calendario_academico': 'La gestión académica es obligatoria.',
            })
        if instance is not None and self._tiene_dependencias(instance):
            estructurales = {
                'calendario_academico', 'curso', 'profesor', 'tipo', 'materia_curso',
            }
            cambiados = {
                campo for campo in estructurales if campo in attrs
                and getattr(instance, f'{campo}_id', getattr(instance, campo, None))
                != getattr(attrs[campo], 'pk', attrs[campo])
            }
            if cambiados:
                raise serializers.ValidationError({
                    'detail': 'La asignación tiene dependencias históricas; no admite cambios estructurales.',
                    'campos': sorted(cambiados),
                })

        if calendario is not None and not calendario.activo:
            raise serializers.ValidationError({'calendario_academico': 'La gestión académica está inactiva.'})

        request = self.context.get('request')
        view = self.context.get('view')
        if curso is not None and view is not None:
            unidad = curso.paralelo.grado.unidad_educativa
            if not view.puede_gestionar_unidad(request.user, unidad):
                raise serializers.ValidationError({'curso': 'No pertenece a su ámbito institucional.'})
        if profesor is not None and curso is not None:
            unidad_id = curso.paralelo.grado.unidad_educativa_id
            if profesor.unidad_id != unidad_id:
                raise serializers.ValidationError({'profesor': 'Pertenece a otra unidad educativa.'})
        if materia_curso is not None and curso is not None and materia_curso.curso_id != curso.pk:
            raise serializers.ValidationError({'materia_curso': 'No corresponde al curso seleccionado.'})

        candidato = AsignacionDocente(
            **{
                campo.name: getattr(instance, campo.name) if instance is not None else campo.default
                for campo in AsignacionDocente._meta.fields
                if campo.name not in {'id', 'created_at', 'updated_at'}
                and not campo.is_relation and campo.has_default()
            }
        )
        if instance is not None:
            candidato = instance
        for campo, valor in attrs.items():
            setattr(candidato, campo, valor)
        try:
            candidato.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs

    @staticmethod
    def _tiene_dependencias(asignacion):
        return (
            asignacion.horarios.exists()
            or asignacion.sesiones.exists()
            or asignacion.actividades_evaluacion.exists()
        )

    def create(self, validated_data):
        instance = AsignacionDocente(**validated_data)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        instance.save()
        return instance


def normalizar_nombre_materia(valor):
    return ' '.join(str(valor or '').split())


class MateriaSerializer(serializers.ModelSerializer):
    unidad_nombre = serializers.CharField(source='unidad_educativa.nombre', read_only=True)

    class Meta:
        model = Materia
        fields = [
            'id', 'unidad_educativa', 'unidad_nombre', 'nombre', 'estado',
            'created_at', 'updated_at', 'eliminado_at',
        ]
        read_only_fields = ['estado', 'created_at', 'updated_at', 'eliminado_at']

    def validate_nombre(self, value):
        value = normalizar_nombre_materia(value)
        if not value:
            raise serializers.ValidationError('El nombre es obligatorio.')
        return value

    def validate(self, attrs):
        unidad = attrs.get('unidad_educativa', getattr(self.instance, 'unidad_educativa', None))
        if unidad is None:
            raise serializers.ValidationError({'unidad_educativa': 'La unidad educativa es obligatoria.'})
        view = self.context.get('view')
        request = self.context.get('request')
        if view is not None and request is not None and not view.puede_gestionar_unidad(request.user, unidad):
            raise serializers.ValidationError({'unidad_educativa': 'No pertenece a su ámbito institucional.'})
        nombre = attrs.get('nombre', getattr(self.instance, 'nombre', ''))
        duplicado = Materia.objects.filter(
            unidad_educativa=unidad, estado=Materia.Estado.ACTIVO, eliminado_at__isnull=True,
            nombre__iexact=nombre,
        )
        if self.instance is not None:
            duplicado = duplicado.exclude(pk=self.instance.pk)
        if duplicado.exists():
            raise serializers.ValidationError({'nombre': 'Ya existe una materia activa con ese nombre en la unidad educativa.'})
        return attrs


class MateriaCursoSerializer(serializers.ModelSerializer):
    curso_nombre = serializers.CharField(source='curso.nombre', read_only=True)
    materia_nombre = serializers.CharField(source='materia.nombre', read_only=True)
    unidad_educativa = serializers.IntegerField(source='curso.paralelo.grado.unidad_educativa_id', read_only=True)

    class Meta:
        model = MateriaCurso
        fields = [
            'id', 'curso', 'curso_nombre', 'materia', 'materia_nombre', 'profesor',
            'unidad_educativa', 'estado', 'created_at', 'updated_at', 'eliminado_at',
        ]
        read_only_fields = ['estado', 'created_at', 'updated_at', 'eliminado_at']

    def validate(self, attrs):
        curso = attrs.get('curso', getattr(self.instance, 'curso', None))
        materia = attrs.get('materia', getattr(self.instance, 'materia', None))
        request = self.context.get('request')
        view = self.context.get('view')
        if curso is not None and view is not None and request is not None:
            unidad = curso.paralelo.grado.unidad_educativa
            if not view.puede_gestionar_unidad(request.user, unidad):
                raise serializers.ValidationError({'curso': 'No pertenece a su ámbito institucional.'})
        if curso is not None and materia is not None:
            if materia.unidad_educativa_id is None:
                raise serializers.ValidationError({'materia': 'La materia histórica sin unidad no admite nuevas relaciones.'})
            if materia.unidad_educativa_id != curso.paralelo.grado.unidad_educativa_id:
                raise serializers.ValidationError({'materia': 'La materia y el curso deben pertenecer a la misma unidad educativa.'})
            if materia.estado != Materia.Estado.ACTIVO or materia.eliminado_at is not None:
                raise serializers.ValidationError({'materia': 'La materia debe estar activa.'})
        return attrs

    def create(self, validated_data):
        instance = MateriaCurso(**validated_data)
        instance.full_clean()
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.full_clean()
        instance.save()
        return instance


class MateriaCursoConsultaSerializer(serializers.ModelSerializer):
    curso_nombre = serializers.CharField(source='curso.nombre', read_only=True)
    materia_nombre = serializers.CharField(source='materia.nombre', read_only=True)

    class Meta:
        model = MateriaCurso
        fields = ['id', 'curso', 'curso_nombre', 'materia', 'materia_nombre']
        read_only_fields = fields


# === HU-15: Configuración de Evaluación ===

class DimensionEvaluacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DimensionEvaluacion
        fields = ['id', 'codigo', 'nombre', 'ponderacion', 'orden', 'estado']
        read_only_fields = ['id', 'estado']


class ConfiguracionEvaluacionSerializer(serializers.ModelSerializer):
    dimensiones = DimensionEvaluacionSerializer(many=True, read_only=True)
    nivel_display = serializers.SerializerMethodField()
    unidad_educativa = serializers.IntegerField(
        source='calendario_academico.unidad_educativa_id', read_only=True,
    )
    unidad_nombre = serializers.CharField(
        source='calendario_academico.unidad_educativa.nombre', read_only=True,
    )
    gestion_anio = serializers.IntegerField(source='calendario_academico.año', read_only=True)

    class Meta:
        model = ConfiguracionEvaluacion
        fields = [
            'id', 'calendario_academico', 'gestion_anio', 'unidad_educativa', 'unidad_nombre',
            'nivel', 'nivel_display', 'nota_minima', 'nota_maxima', 'nota_aprobacion',
            'decimales', 'regla_redondeo', 'estado', 'dimensiones',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['estado', 'created_at', 'updated_at']

    def get_nivel_display(self, obj):
        return dict(Grado.NIVELES_EDUCATIVOS).get(obj.nivel, obj.nivel)


class DimensionEvaluacionInputSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=30)
    nombre = serializers.CharField(max_length=100)
    ponderacion = serializers.DecimalField(
        max_digits=7, decimal_places=2, min_value=Decimal('0.01'), max_value=Decimal('100'),
    )
    orden = serializers.IntegerField(min_value=1)


class ConfigurarEvaluacionSerializer(serializers.Serializer):
    """Reemplaza de forma atómica la configuración y las 5 dimensiones de una
    gestión académica + nivel. No es un ModelSerializer porque escribe sobre
    dos modelos (ConfiguracionEvaluacion y DimensionEvaluacion) a la vez."""

    calendario_academico = serializers.PrimaryKeyRelatedField(
        queryset=CalendarioAcademico.objects.all(),
    )
    nivel = serializers.ChoiceField(choices=Grado.NIVELES_EDUCATIVOS)
    nota_minima = serializers.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    nota_maxima = serializers.DecimalField(max_digits=7, decimal_places=2, default=Decimal('100'))
    nota_aprobacion = serializers.DecimalField(max_digits=7, decimal_places=2, default=Decimal('51'))
    decimales = serializers.IntegerField(min_value=0, max_value=4, default=0)
    regla_redondeo = serializers.ChoiceField(
        choices=ConfiguracionEvaluacion.ReglaRedondeo.choices,
        default=ConfiguracionEvaluacion.ReglaRedondeo.NORMAL,
    )
    dimensiones = DimensionEvaluacionInputSerializer(many=True)

    def validate_dimensiones(self, value):
        if len(value) != 5:
            raise serializers.ValidationError('Debe definir exactamente 5 dimensiones.')
        codigos = [dato['codigo'].strip().upper() for dato in value]
        if len(set(codigos)) != len(codigos):
            raise serializers.ValidationError('Los códigos de dimensión no pueden repetirse.')
        total = sum((dato['ponderacion'] for dato in value), Decimal('0'))
        if total != Decimal('100'):
            raise serializers.ValidationError(
                f'La suma de las ponderaciones debe ser exactamente 100 (actual: {total}).',
            )
        return value

    def validate(self, attrs):
        if attrs['nota_minima'] >= attrs['nota_maxima']:
            raise serializers.ValidationError(
                {'nota_maxima': 'Debe ser mayor que la nota mínima.'},
            )
        if not (attrs['nota_minima'] <= attrs['nota_aprobacion'] <= attrs['nota_maxima']):
            raise serializers.ValidationError(
                {'nota_aprobacion': 'Debe estar entre la nota mínima y la nota máxima.'},
            )

        calendario = attrs['calendario_academico']
        view = self.context.get('view')
        request = self.context.get('request')
        if view is not None and not view.puede_gestionar_unidad(
            request.user, calendario.unidad_educativa,
        ):
            raise serializers.ValidationError(
                {'calendario_academico': 'No pertenece a su ámbito institucional.'},
            )

        existente = ConfiguracionEvaluacion.objects.filter(
            calendario_academico=calendario, nivel=attrs['nivel'],
        ).first()
        if existente is not None and existente.dimensiones.filter(
            actividades__isnull=False,
        ).exists():
            raise serializers.ValidationError(
                'No se puede reconfigurar: ya existen actividades evaluativas '
                'registradas con las dimensiones vigentes.',
            )
        return attrs

    def save(self):
        validated = dict(self.validated_data)
        dimensiones = validated.pop('dimensiones')
        configuracion, _ = ConfiguracionEvaluacion.objects.update_or_create(
            calendario_academico=validated.pop('calendario_academico'),
            nivel=validated.pop('nivel'),
            defaults=validated,
        )
        configuracion.dimensiones.all().delete()
        DimensionEvaluacion.objects.bulk_create([
            DimensionEvaluacion(
                configuracion=configuracion,
                codigo=dato['codigo'].strip().upper(),
                nombre=dato['nombre'].strip(),
                ponderacion=dato['ponderacion'],
                orden=dato['orden'],
            )
            for dato in dimensiones
        ])
        return configuracion


# === HU-16: Actividades y Calificaciones ===

class ActividadEvaluacionSerializer(serializers.ModelSerializer):
    dimension_codigo = serializers.CharField(source='dimension.codigo', read_only=True)
    dimension_nombre = serializers.CharField(source='dimension.nombre', read_only=True)
    materia_nombre = serializers.CharField(
        source='asignacion_docente.materia_curso.materia.nombre', read_only=True,
    )
    curso_nombre = serializers.CharField(source='asignacion_docente.curso.nombre', read_only=True)
    periodo_nombre = serializers.CharField(source='periodo.nombre', read_only=True)

    class Meta:
        model = ActividadEvaluacion
        fields = [
            'id', 'asignacion_docente', 'curso_nombre', 'materia_nombre',
            'periodo', 'periodo_nombre', 'dimension', 'dimension_codigo',
            'dimension_nombre', 'nombre', 'descripcion', 'fecha', 'puntaje_maximo',
            'estado', 'created_at', 'updated_at',
        ]
        read_only_fields = ['estado', 'created_at', 'updated_at']

    def validate(self, attrs):
        asignacion = attrs.get(
            'asignacion_docente', getattr(self.instance, 'asignacion_docente', None),
        )
        if asignacion is not None and asignacion.tipo != AsignacionDocente.Tipo.MATERIA:
            raise serializers.ValidationError({
                'asignacion_docente': (
                    'Solo se pueden crear actividades de evaluación sobre '
                    'asignaciones de materia, no de tutoría de curso.'
                ),
            })

        request = self.context.get('request')
        view = self.context.get('view')
        if asignacion is not None and view is not None and not view.puede_gestionar_asignacion(
            request.user, asignacion,
        ):
            raise serializers.ValidationError(
                {'asignacion_docente': 'No pertenece a su carga docente.'},
            )

        instancia = self.instance or ActividadEvaluacion()
        for campo, valor in attrs.items():
            setattr(instancia, campo, valor)
        try:
            instancia.full_clean(exclude=['created_by', 'created_by_snapshot'])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        usuario = getattr(request, 'user', None)
        validated_data['created_by'] = usuario if usuario and usuario.is_authenticated else None
        validated_data['created_by_snapshot'] = str(usuario) if usuario and usuario.is_authenticated else None
        return super().create(validated_data)


class CalificacionSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(
        source='historial_inscripcion.estudiante.usuario.get_full_name', read_only=True,
    )
    actividad_nombre = serializers.CharField(source='actividad.nombre', read_only=True)

    class Meta:
        model = Calificacion
        fields = [
            'id', 'actividad', 'actividad_nombre', 'historial_inscripcion',
            'estudiante_nombre', 'valor', 'estado', 'registrada_at', 'updated_at',
        ]
        read_only_fields = ['estado', 'registrada_at', 'updated_at']

    def validate(self, attrs):
        actividad = attrs.get('actividad', getattr(self.instance, 'actividad', None))

        request = self.context.get('request')
        view = self.context.get('view')
        if actividad is not None and view is not None and not view.puede_gestionar_asignacion(
            request.user, actividad.asignacion_docente,
        ):
            raise serializers.ValidationError({'actividad': 'No pertenece a su carga docente.'})

        instancia = self.instance or Calificacion()
        for campo, valor in attrs.items():
            setattr(instancia, campo, valor)
        try:
            instancia.full_clean(exclude=['estado'])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


class CalificacionMasivaItemSerializer(serializers.Serializer):
    historial_inscripcion = serializers.PrimaryKeyRelatedField(
        queryset=HistorialInscripcion.objects.all(),
    )
    valor = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal('0'))


class GuardarCalificacionesSerializer(serializers.Serializer):
    """Carga masiva de notas de una columna (actividad) del cuaderno
    pedagógico. No es un ModelSerializer: valida y guarda en bloque."""

    calificaciones = CalificacionMasivaItemSerializer(many=True)

    def validate_calificaciones(self, value):
        if not value:
            raise serializers.ValidationError('Debe enviar al menos una calificación.')
        ids = [dato['historial_inscripcion'].pk for dato in value]
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError(
                'No puede repetir al mismo estudiante en la misma carga.',
            )
        return value

    def guardar(self, actividad):
        guardadas = []
        for dato in self.validated_data['calificaciones']:
            historial = dato['historial_inscripcion']
            valor = dato['valor']
            if valor > actividad.puntaje_maximo:
                raise serializers.ValidationError({
                    'valor': (
                        f'La nota no puede superar {actividad.puntaje_maximo} '
                        f'en "{actividad.nombre}".'
                    ),
                })
            if historial.curso_nuevo_id != actividad.asignacion_docente.curso_id:
                raise serializers.ValidationError({
                    'historial_inscripcion': 'El estudiante no pertenece al curso de la actividad.',
                })
            calificacion, _ = Calificacion.objects.update_or_create(
                actividad=actividad, historial_inscripcion=historial,
                defaults={'valor': valor},
            )
            guardadas.append(calificacion)
        return guardadas

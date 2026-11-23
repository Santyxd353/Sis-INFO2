from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied

from aplicaciones.calendario.models import Periodo
from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.usuarios.permissions import PermisoPorPuesto, PermisoPorRol, metodo_a_accion
from aplicaciones.usuarios.tenancy import es_superadmin, normalizar_nombre, unidades_permitidas, validar_unidad
from aplicaciones.usuarios.feature_access import id_filters

from aplicaciones.usuarios.auditoria import registrar_evento

from . import resultados as servicio_resultados
from .models import (
    ActividadEvaluacion, AsignacionDocente, Calificacion,
    ConfiguracionEvaluacion, Curso, Grado, Materia, MateriaCurso, Paralelo,
    ResultadoTrimestral,
)
from .serializers import (
    ActividadEvaluacionSerializer, AsignacionDocenteSerializer,
    CalificacionSerializer, ConfigurarEvaluacionSerializer,
    ConfiguracionEvaluacionSerializer, CursoSerializer, GradoSerializer,
    GuardarCalificacionesSerializer, MateriaCursoConsultaSerializer,
    ParaleloSerializer, MateriaSerializer, MateriaCursoSerializer,
)


class PermisoAsignacionDocente(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        if es_superadmin(user):
            return True
        from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
        autorizar_acceso_modelo(user, 'asignacion-docente')
        if hasattr(user, 'admin'):
            from aplicaciones.usuarios.privilegios import puede
            accion = 'listar' if request.method in SAFE_METHODS else (
                'crear' if request.method == 'POST' and view.action == 'create' else 'editar'
            )
            return puede(user, 'asignacion-docente', accion)
        return hasattr(user, 'profesor') and request.method in SAFE_METHODS


class PermisoMateriaInstitucional(BasePermission):
    """Permisos separados para materias y materias por curso."""

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        if es_superadmin(user):
            return request.method in SAFE_METHODS
        recurso = view.basename
        accion = 'desactivar' if getattr(view, 'action', None) == 'desactivar' else metodo_a_accion(request.method)
        from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
        from aplicaciones.usuarios.privilegios import puede
        autorizar_acceso_modelo(user, recurso)
        if hasattr(user, 'admin'):
            return puede(user, recurso, accion)
        if hasattr(user, 'profesor'):
            if request.method not in SAFE_METHODS:
                return False
            return puede(user, recurso, 'listar')
        return False


class AsignacionDocentePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def unidades_academicas_permitidas(user):
    permitidas = unidades_permitidas(user)
    return None if permitidas is None else list(permitidas)


class GradoViewSet(ModelViewSet):
    serializer_class = GradoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoPorPuesto & PermisoPorRol]

    def get_queryset(self):
        queryset = Grado.objects.select_related('unidad_educativa').all().order_by(
            'nivel_educativo', 'numero'
        )
        permitidas = unidades_permitidas(self.request.user)
        if permitidas is not None:
            queryset = queryset.filter(unidad_educativa_id__in=permitidas)
        unidad_id = self.request.query_params.get('unidad_educativa')
        return queryset.filter(unidad_educativa_id=unidad_id) if unidad_id else queryset

    def perform_create(self, serializer):
        unidad = serializer.validated_data['unidad_educativa']
        validar_unidad(self.request.user, unidad)
        serializer.save()

    def perform_update(self, serializer):
        unidad = serializer.validated_data.get('unidad_educativa', serializer.instance.unidad_educativa)
        validar_unidad(self.request.user, unidad)
        serializer.save()


class ParaleloViewSet(ModelViewSet):
    serializer_class = ParaleloSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoPorPuesto & PermisoPorRol]

    def get_queryset(self):
        queryset = Paralelo.objects.select_related('grado', 'grado__unidad_educativa').all()
        permitidas = unidades_permitidas(self.request.user)
        if permitidas is not None:
            queryset = queryset.filter(grado__unidad_educativa_id__in=permitidas)
        grado_id = self.request.query_params.get('grado')
        return queryset.filter(grado_id=grado_id) if grado_id else queryset

    def perform_create(self, serializer):
        grado = serializer.validated_data['grado']
        validar_unidad(self.request.user, grado.unidad_educativa)
        serializer.save()

    def perform_update(self, serializer):
        grado = serializer.validated_data.get('grado', serializer.instance.grado)
        validar_unidad(self.request.user, grado.unidad_educativa)
        serializer.save()


class PermisoCatalogoCursos(BasePermission):
    """El catalogo administrativo no es el portal de autoservicio estudiantil."""

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        rol = normalizar_nombre(getattr(getattr(user, 'rol', None), 'nombre', ''))
        return rol != 'estudiante' and not hasattr(user, 'estudiante')


class CursoViewSet(ModelViewSet):
    serializer_class = CursoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoCatalogoCursos, PermisoPorPuesto & PermisoPorRol]

    def get_queryset(self):
        queryset = Curso.objects.select_related(
            'paralelo',
            'paralelo__grado',
            'paralelo__grado__unidad_educativa',
            'tutor',
        ).all().order_by('nombre')
        user = self.request.user
        permitidas = unidades_permitidas(user)
        if permitidas is not None:
            queryset = queryset.filter(
                paralelo__grado__unidad_educativa_id__in=permitidas
            )
            if hasattr(user, 'profesor'):
                queryset = queryset.filter(tutor=user.profesor)
            elif hasattr(user, 'estudiante'):
                queryset = queryset.filter(pk=user.estudiante.curso_id)
            elif hasattr(user, 'tutor'):
                queryset = queryset.filter(estudiantes__tutores__tutor=user.tutor).distinct()
        paralelo_id = self.request.query_params.get('paralelo')
        queryset = id_filters(queryset, self.request.query_params, {
            'unidad_educativa': 'paralelo__grado__unidad_educativa_id',
        })
        return queryset.filter(paralelo_id=paralelo_id) if paralelo_id else queryset

    def perform_create(self, serializer):
        paralelo = serializer.validated_data['paralelo']
        validar_unidad(self.request.user, paralelo.grado.unidad_educativa)
        profesor = serializer.validated_data.get('tutor')
        if profesor and profesor.unidad_id != paralelo.grado.unidad_educativa_id:
            raise serializers.ValidationError({'tutor': 'El docente tutor debe pertenecer a la unidad educativa del curso.'})
        serializer.save()

    def perform_update(self, serializer):
        paralelo = serializer.validated_data.get('paralelo', serializer.instance.paralelo)
        validar_unidad(self.request.user, paralelo.grado.unidad_educativa)
        profesor = serializer.validated_data.get('tutor', serializer.instance.tutor)
        if profesor and profesor.unidad_id != paralelo.grado.unidad_educativa_id:
            raise serializers.ValidationError({'tutor': 'El docente tutor debe pertenecer a la unidad educativa del curso.'})
        serializer.save()


class AsignacionDocenteViewSet(ModelViewSet):
    serializer_class = AsignacionDocenteSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoAsignacionDocente]
    pagination_class = AsignacionDocentePagination
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    @staticmethod
    def puede_gestionar_unidad(user, unidad):
        permitidas = unidades_academicas_permitidas(user)
        return permitidas is None or unidad.pk in permitidas

    def get_queryset(self):
        queryset = AsignacionDocente.objects.select_related(
            'calendario_academico', 'calendario_academico__unidad_educativa',
            'curso', 'curso__paralelo', 'curso__paralelo__grado',
            'curso__paralelo__grado__unidad_educativa',
            'materia_curso', 'materia_curso__materia',
            'profesor', 'profesor__usuario',
        ).order_by('-fecha_inicio', '-pk')
        user = self.request.user
        if not es_superadmin(user):
            if hasattr(user, 'profesor'):
                queryset = queryset.filter(profesor=user.profesor)
            elif hasattr(user, 'admin'):
                permitidas = unidades_permitidas(user)
                queryset = queryset.filter(
                    curso__paralelo__grado__unidad_educativa_id__in=permitidas,
                )
            else:
                return queryset.none()

        params = self.request.query_params
        filtros_id = {
            'profesor': 'profesor_id', 'curso': 'curso_id',
            'materia_curso': 'materia_curso_id',
            'materia': 'materia_curso__materia_id',
            'calendario_academico': 'calendario_academico_id',
            'gestion': 'calendario_academico_id',
            'unidad_educativa': 'curso__paralelo__grado__unidad_educativa_id',
        }
        for parametro, campo in filtros_id.items():
            valor = params.get(parametro)
            if valor in (None, ''):
                continue
            try:
                valor = int(valor)
            except (TypeError, ValueError):
                raise serializers.ValidationError({parametro: 'Debe ser un entero positivo.'})
            if valor <= 0:
                raise serializers.ValidationError({parametro: 'Debe ser un entero positivo.'})
            queryset = queryset.filter(**{campo: valor})

        tipo = params.get('tipo')
        if tipo:
            if tipo not in AsignacionDocente.Tipo.values:
                raise serializers.ValidationError({'tipo': 'Tipo de asignación inválido.'})
            queryset = queryset.filter(tipo=tipo)
        estado = params.get('estado')
        if estado:
            if estado not in {'ACTIVO', 'INACTIVO'}:
                raise serializers.ValidationError({'estado': 'Estado inválido.'})
            queryset = queryset.filter(estado=estado)
        vigente = params.get('vigente')
        if vigente:
            fecha = parse_date(vigente)
            if fecha is None:
                raise serializers.ValidationError({'vigente': 'Use una fecha ISO válida.'})
            queryset = queryset.filter(
                fecha_inicio__lte=fecha, estado='ACTIVO', eliminado_at__isnull=True,
            ).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha))
        return queryset

    def _unidad(self, asignacion):
        return asignacion.curso.paralelo.grado.unidad_educativa

    def perform_create(self, serializer):
        with transaction.atomic():
            asignacion = serializer.save()
            registrar_evento(
                accion='CREAR', entidad='ASIGNACION_DOCENTE', request=self.request,
                entidad_id=asignacion.pk, unidad=self._unidad(asignacion),
                cambios={'campos': serializer.validated_data.keys()},
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            asignacion = serializer.save()
            registrar_evento(
                accion='ACTUALIZAR', entidad='ASIGNACION_DOCENTE', request=self.request,
                entidad_id=asignacion.pk, unidad=self._unidad(asignacion),
                cambios={'campos': serializer.validated_data.keys()},
            )

    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        asignacion = self.get_object()
        if asignacion.estado != 'ACTIVO':
            raise serializers.ValidationError({'estado': 'La asignación ya está inactiva.'})
        with transaction.atomic():
            asignacion.estado = 'INACTIVO'
            asignacion.eliminado_at = timezone.now()
            if asignacion.fecha_fin is None:
                fecha = max(timezone.localdate(), asignacion.fecha_inicio)
                if asignacion.calendario_academico_id:
                    fecha = min(fecha, asignacion.calendario_academico.fecha_fin)
                asignacion.fecha_fin = fecha
            try:
                asignacion.full_clean()
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict)
            asignacion.save(update_fields=['estado', 'eliminado_at', 'fecha_fin', 'updated_at'])
            registrar_evento(
                accion='DESACTIVAR', entidad='ASIGNACION_DOCENTE', request=request,
                entidad_id=asignacion.pk, unidad=self._unidad(asignacion),
                cambios={
                    'campos': ('estado', 'fecha_fin', 'eliminado_at'),
                    'estado_anterior': 'ACTIVO', 'estado_nuevo': 'INACTIVO',
                },
            )
        return Response(self.get_serializer(asignacion).data, status=status.HTTP_200_OK)


class MateriaScopeMixin:
    @staticmethod
    def puede_gestionar_unidad(user, unidad):
        permitidas = unidades_academicas_permitidas(user)
        return permitidas is None or unidad.pk in permitidas

    def _filtrar_unidad(self, queryset, campo):
        permitidas = unidades_academicas_permitidas(self.request.user)
        if permitidas is not None:
            queryset = queryset.filter(**{f'{campo}__in': permitidas})
        return queryset


class MateriaViewSet(MateriaScopeMixin, ModelViewSet):
    serializer_class = MateriaSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoMateriaInstitucional]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        queryset = Materia.objects.select_related('unidad_educativa', 'unidad_educativa__colegio').order_by('nombre', 'pk')
        user = self.request.user
        if hasattr(user, 'profesor') and not es_superadmin(user):
            queryset = queryset.filter(
                cursos__asignaciones_docentes__profesor=user.profesor,
            ).distinct()
        else:
            queryset = self._filtrar_unidad(queryset, 'unidad_educativa_id')
        queryset = id_filters(queryset, self.request.query_params, {'unidad_educativa': 'unidad_educativa_id'})
        estado = self.request.query_params.get('estado')
        if estado:
            if estado not in Materia.Estado.values:
                raise serializers.ValidationError({'estado': 'Estado inválido.'})
            queryset = queryset.filter(estado=estado)
        nombre = self.request.query_params.get('nombre')
        if nombre:
            queryset = queryset.filter(nombre__icontains=nombre.strip())
        return queryset

    def _registrar(self, accion, materia, cambios):
        registrar_evento(
            accion=accion, entidad='MATERIA', request=self.request, entidad_id=materia.pk,
            unidad=materia.unidad_educativa, cambios=cambios,
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            materia = serializer.save()
            self._registrar('CREAR', materia, {'campos': serializer.validated_data.keys()})

    def perform_update(self, serializer):
        with transaction.atomic():
            materia = serializer.save()
            self._registrar('ACTUALIZAR', materia, {'campos': serializer.validated_data.keys()})

    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        materia = self.get_object()
        if materia.unidad_educativa_id is None:
            raise serializers.ValidationError({'detail': 'La materia histórica requiere conciliación antes de desactivarse.'})
        if materia.cursos.filter(estado=MateriaCurso.Estado.ACTIVO, eliminado_at__isnull=True).exists():
            raise serializers.ValidationError({'detail': 'No puede desactivarse mientras tenga materias por curso activas.'})
        with transaction.atomic():
            materia.estado = Materia.Estado.INACTIVO
            materia.eliminado_at = timezone.now()
            materia.save(update_fields=['estado', 'eliminado_at', 'updated_at'])
            self._registrar('DESACTIVAR', materia, {'campos': ('estado', 'eliminado_at'), 'estado_nuevo': 'INACTIVO'})
        return Response(self.get_serializer(materia).data)


class MateriaCursoConsultaViewSet(MateriaScopeMixin, ModelViewSet):
    serializer_class = MateriaCursoConsultaSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoMateriaInstitucional]
    pagination_class = AsignacionDocentePagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        return MateriaCursoConsultaSerializer if self.action in {'list', 'retrieve'} else MateriaCursoSerializer

    def get_queryset(self):
        queryset = MateriaCurso.objects.select_related(
            'curso', 'curso__paralelo', 'curso__paralelo__grado',
            'curso__paralelo__grado__unidad_educativa', 'materia',
        ).order_by('materia__nombre', 'pk')
        user = self.request.user
        if hasattr(user, 'profesor') and not es_superadmin(user):
            queryset = queryset.filter(asignaciones_docentes__profesor=user.profesor).distinct()
        else:
            queryset = self._filtrar_unidad(queryset, 'curso__paralelo__grado__unidad_educativa_id')

        for parametro, campo in {'curso': 'curso_id', 'materia': 'materia_id'}.items():
            valor = self.request.query_params.get(parametro)
            if valor in (None, ''):
                continue
            try:
                valor = int(valor)
            except (TypeError, ValueError):
                raise serializers.ValidationError({parametro: 'Debe ser un entero positivo.'})
            if valor <= 0:
                raise serializers.ValidationError({parametro: 'Debe ser un entero positivo.'})
            queryset = queryset.filter(**{campo: valor})
        queryset = id_filters(queryset, self.request.query_params, {
            'unidad_educativa': 'curso__paralelo__grado__unidad_educativa_id',
        })
        estado = self.request.query_params.get('estado')
        if estado:
            if estado not in MateriaCurso.Estado.values:
                raise serializers.ValidationError({'estado': 'Estado inválido.'})
            queryset = queryset.filter(estado=estado)
        return queryset

    def _unidad(self, materia_curso):
        return materia_curso.curso.paralelo.grado.unidad_educativa

    def _registrar(self, accion, materia_curso, cambios):
        registrar_evento(
            accion=accion, entidad='MATERIA_CURSO', request=self.request,
            entidad_id=materia_curso.pk, unidad=self._unidad(materia_curso), cambios=cambios,
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            materia_curso = serializer.save()
            self._registrar('CREAR', materia_curso, {'campos': serializer.validated_data.keys()})

    def perform_update(self, serializer):
        with transaction.atomic():
            materia_curso = serializer.save()
            self._registrar('ACTUALIZAR', materia_curso, {'campos': serializer.validated_data.keys()})

    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        materia_curso = self.get_object()
        dependiente = (
            materia_curso.asignaciones_docentes.filter(estado='ACTIVO', eliminado_at__isnull=True).exists()
            or materia_curso.asignaciones_docentes.filter(horarios__isnull=False).exists()
            or materia_curso.asignaciones_docentes.filter(sesiones__isnull=False).exists()
            or materia_curso.asignaciones_docentes.filter(actividades_evaluacion__isnull=False).exists()
        )
        if dependiente:
            raise serializers.ValidationError({'detail': 'No puede desactivarse mientras tenga dependencias académicas.'})
        with transaction.atomic():
            materia_curso.estado = MateriaCurso.Estado.INACTIVO
            materia_curso.eliminado_at = timezone.now()
            materia_curso.save(update_fields=['estado', 'eliminado_at', 'updated_at'])
            self._registrar('DESACTIVAR', materia_curso, {'campos': ('estado', 'eliminado_at'), 'estado_nuevo': 'INACTIVO'})
        return Response(self.get_serializer(materia_curso).data)


class PermisoConfiguracionEvaluacion(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        if es_superadmin(user):
            return True
        from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
        autorizar_acceso_modelo(user, 'configuracion-evaluacion')
        return hasattr(user, 'admin')


class ConfiguracionEvaluacionViewSet(ModelViewSet):
    """HU-15: configuración de dimensiones de evaluación por gestión académica y nivel."""

    serializer_class = ConfiguracionEvaluacionSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoConfiguracionEvaluacion]
    http_method_names = ['get', 'put', 'head', 'options']

    @staticmethod
    def puede_gestionar_unidad(user, unidad):
        permitidas = unidades_academicas_permitidas(user)
        return permitidas is None or unidad.pk in permitidas

    def get_queryset(self):
        queryset = ConfiguracionEvaluacion.objects.select_related(
            'calendario_academico', 'calendario_academico__unidad_educativa',
        ).prefetch_related('dimensiones').order_by('-calendario_academico__año', 'nivel')
        permitidas = unidades_academicas_permitidas(self.request.user)
        if permitidas is not None:
            queryset = queryset.filter(
                calendario_academico__unidad_educativa_id__in=permitidas,
            )

        filtros_id = {
            'calendario_academico': 'calendario_academico_id',
            'unidad_educativa': 'calendario_academico__unidad_educativa_id',
        }
        for parametro, campo in filtros_id.items():
            valor = self.request.query_params.get(parametro)
            if valor in (None, ''):
                continue
            try:
                valor = int(valor)
            except (TypeError, ValueError):
                raise serializers.ValidationError({parametro: 'Debe ser un entero positivo.'})
            queryset = queryset.filter(**{campo: valor})

        nivel = self.request.query_params.get('nivel')
        if nivel:
            queryset = queryset.filter(nivel=nivel)
        return queryset

    @action(detail=False, methods=['put'], url_path='configurar')
    def configurar(self, request):
        serializer = ConfigurarEvaluacionSerializer(
            data=request.data, context={'request': request, 'view': self},
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            configuracion = serializer.save()
            registrar_evento(
                accion='ACTUALIZAR', entidad='CONFIGURACION_EVALUACION', request=request,
                entidad_id=configuracion.pk,
                unidad=configuracion.calendario_academico.unidad_educativa,
                cambios={'campos': ('nivel', 'dimensiones')},
            )
        return Response(
            ConfiguracionEvaluacionSerializer(configuracion).data, status=status.HTTP_200_OK,
        )


class PermisoEvaluacionDocente(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        if es_superadmin(user):
            return True
        from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
        autorizar_acceso_modelo(user, getattr(view, 'basename', None) or 'actividad-evaluacion')
        if hasattr(user, 'admin'):
            return request.method in SAFE_METHODS
        return hasattr(user, 'profesor')


class ActividadEvaluacionViewSet(ModelViewSet):
    """HU-16: actividades evaluativas del cuaderno pedagógico."""

    serializer_class = ActividadEvaluacionSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoEvaluacionDocente]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    @staticmethod
    def puede_gestionar_asignacion(user, asignacion):
        if es_superadmin(user):
            return True
        if hasattr(user, 'profesor'):
            return asignacion.profesor_id == user.profesor.pk
        if hasattr(user, 'admin'):
            permitidas = unidades_academicas_permitidas(user)
            unidad_id = asignacion.curso.paralelo.grado.unidad_educativa_id
            return permitidas is None or unidad_id in permitidas
        return False

    def get_queryset(self):
        queryset = ActividadEvaluacion.objects.select_related(
            'asignacion_docente', 'asignacion_docente__curso',
            'asignacion_docente__curso__paralelo__grado',
            'asignacion_docente__materia_curso__materia', 'asignacion_docente__profesor',
            'periodo', 'periodo__calendario', 'dimension', 'dimension__configuracion',
        ).order_by('-fecha', '-pk')
        user = self.request.user
        if not es_superadmin(user):
            if hasattr(user, 'profesor'):
                queryset = queryset.filter(asignacion_docente__profesor=user.profesor)
            elif hasattr(user, 'admin'):
                permitidas = unidades_academicas_permitidas(user)
                if permitidas is not None:
                    queryset = queryset.filter(
                        asignacion_docente__curso__paralelo__grado__unidad_educativa_id__in=permitidas,
                    )
            else:
                return queryset.none()

        params = self.request.query_params
        filtros_id = {
            'asignacion_docente': 'asignacion_docente_id', 'periodo': 'periodo_id',
            'curso': 'asignacion_docente__curso_id', 'dimension': 'dimension_id',
        }
        for parametro, campo in filtros_id.items():
            valor = params.get(parametro)
            if valor:
                queryset = queryset.filter(**{campo: valor})
        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            actividad = serializer.save()
            registrar_evento(
                accion='CREAR', entidad='ACTIVIDAD_EVALUACION', request=self.request,
                entidad_id=actividad.pk, unidad=self._unidad(actividad),
                cambios={'campos': serializer.validated_data.keys()},
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            actividad = serializer.save()
            registrar_evento(
                accion='ACTUALIZAR', entidad='ACTIVIDAD_EVALUACION', request=self.request,
                entidad_id=actividad.pk, unidad=self._unidad(actividad),
                cambios={'campos': serializer.validated_data.keys()},
            )

    @staticmethod
    def _unidad(actividad):
        return actividad.asignacion_docente.curso.paralelo.grado.unidad_educativa

    @action(detail=False, methods=['get'], url_path='grilla')
    def grilla(self, request):
        """Cuaderno pedagógico: estudiantes x actividades, con el resultado
        trimestral (HU-17) ya calculado para la materia y periodo."""
        asignacion_id = request.query_params.get('asignacion_docente')
        periodo_id = request.query_params.get('periodo')
        if not asignacion_id or not periodo_id:
            raise serializers.ValidationError(
                {'detail': 'Se requieren los parámetros asignacion_docente y periodo.'},
            )
        asignacion = get_object_or_404(AsignacionDocente, pk=asignacion_id)
        if not self.puede_gestionar_asignacion(request.user, asignacion):
            raise PermissionDenied('No pertenece a su carga docente.')
        periodo = get_object_or_404(Periodo, pk=periodo_id)

        actividades = list(
            self.get_queryset().filter(asignacion_docente=asignacion, periodo=periodo)
            .order_by('dimension__orden', 'fecha'),
        )
        estudiantes = Estudiante.objects.filter(curso=asignacion.curso).select_related(
            'usuario',
        ).order_by('usuario__apellido', 'usuario__nombre')

        calificaciones = {
            (c.actividad_id, c.historial_inscripcion.estudiante_id): c
            for c in Calificacion.objects.filter(
                actividad__in=actividades,
            ).select_related('historial_inscripcion')
        }
        resultados_por_estudiante = {}
        if asignacion.materia_curso_id:
            materia = asignacion.materia_curso.materia
            resultados_por_estudiante = {
                r.historial_inscripcion.estudiante_id: r
                for r in ResultadoTrimestral.objects.filter(
                    materia=materia, periodo=periodo,
                    historial_inscripcion__estudiante__curso=asignacion.curso,
                ).select_related('historial_inscripcion')
            }

        filas = []
        for estudiante in estudiantes:
            resultado = resultados_por_estudiante.get(estudiante.pk)
            historial = servicio_resultados.historial_actual(estudiante)
            filas.append({
                'estudiante': estudiante.pk,
                'estudiante_nombre': str(estudiante.usuario),
                'historial_inscripcion': historial.pk if historial else None,
                'notas': {
                    actividad.pk: (
                        str(calificaciones[(actividad.pk, estudiante.pk)].valor)
                        if (actividad.pk, estudiante.pk) in calificaciones else None
                    )
                    for actividad in actividades
                },
                'resultado_trimestral': str(resultado.resultado) if resultado else None,
                'condicion': resultado.condicion if resultado else None,
            })

        return Response({
            'actividades': ActividadEvaluacionSerializer(actividades, many=True).data,
            'estudiantes': filas,
        })

    @action(detail=True, methods=['put'], url_path='calificaciones')
    def calificaciones_masivas(self, request, pk=None):
        """Carga masiva (autoguardado) de las notas de una columna del cuaderno."""
        actividad = self.get_object()
        serializer = GuardarCalificacionesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            guardadas = serializer.guardar(actividad)
            for calificacion in guardadas:
                servicio_resultados.recalcular_por_calificacion(calificacion)
            registrar_evento(
                accion='ACTUALIZAR', entidad='CALIFICACION', request=request,
                entidad_id=actividad.pk, unidad=self._unidad(actividad),
                cambios={'campos': ('calificaciones',)},
            )
        return Response(CalificacionSerializer(guardadas, many=True).data, status=status.HTTP_200_OK)


class CalificacionViewSet(ModelViewSet):
    """HU-16: CRUD individual de calificaciones (complementa la carga masiva)."""

    serializer_class = CalificacionSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoEvaluacionDocente]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    @staticmethod
    def puede_gestionar_asignacion(user, asignacion):
        return ActividadEvaluacionViewSet.puede_gestionar_asignacion(user, asignacion)

    def get_queryset(self):
        queryset = Calificacion.objects.select_related(
            'actividad', 'actividad__asignacion_docente',
            'actividad__asignacion_docente__curso__paralelo__grado',
            'actividad__asignacion_docente__materia_curso__materia', 'actividad__periodo',
            'historial_inscripcion', 'historial_inscripcion__estudiante__usuario',
        ).order_by('-registrada_at')
        user = self.request.user
        if not es_superadmin(user):
            if hasattr(user, 'profesor'):
                queryset = queryset.filter(actividad__asignacion_docente__profesor=user.profesor)
            elif hasattr(user, 'admin'):
                permitidas = unidades_academicas_permitidas(user)
                if permitidas is not None:
                    queryset = queryset.filter(
                        actividad__asignacion_docente__curso__paralelo__grado__unidad_educativa_id__in=permitidas,
                    )
            else:
                return queryset.none()
        actividad_id = self.request.query_params.get('actividad')
        if actividad_id:
            queryset = queryset.filter(actividad_id=actividad_id)
        return queryset

    @staticmethod
    def _unidad(calificacion):
        return calificacion.actividad.asignacion_docente.curso.paralelo.grado.unidad_educativa

    def perform_create(self, serializer):
        with transaction.atomic():
            calificacion = serializer.save()
            servicio_resultados.recalcular_por_calificacion(calificacion)
            registrar_evento(
                accion='CREAR', entidad='CALIFICACION', request=self.request,
                entidad_id=calificacion.pk, unidad=self._unidad(calificacion),
                cambios={'campos': ('valor',)},
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            calificacion = serializer.save()
            servicio_resultados.recalcular_por_calificacion(calificacion)
            registrar_evento(
                accion='ACTUALIZAR', entidad='CALIFICACION', request=self.request,
                entidad_id=calificacion.pk, unidad=self._unidad(calificacion),
                cambios={'campos': ('valor',)},
            )

    def perform_destroy(self, instance):
        materia = instance.actividad.asignacion_docente.materia_curso.materia
        periodo = instance.actividad.periodo
        historial = instance.historial_inscripcion
        unidad = self._unidad(instance)
        pk = instance.pk
        with transaction.atomic():
            instance.delete()
            servicio_resultados.calcular_resultado_trimestral(historial, materia, periodo)
            registrar_evento(
                accion='ELIMINAR', entidad='CALIFICACION', request=self.request,
                entidad_id=pk, unidad=unidad, cambios={'campos': ('valor',)},
            )

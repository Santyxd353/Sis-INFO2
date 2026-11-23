"""HU-12: weekly schedules, scoped catalogs and serialized conflict checks."""
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from aplicaciones.institucion.models import Aula, Colegio, Modulo, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.auditoria import registrar_evento
from aplicaciones.usuarios.feature_access import SchoolPagination, full_name, granted, id_filters, scoped
from aplicaciones.usuarios.tenancy import es_superadmin
from .models import AsignacionDocente, BloqueHorario, Curso, HorarioClase


class HorarioConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'El horario cambió o tiene dependencias. Actualice e intente nuevamente.'


class HorarioPermission(BasePermission):
    def has_permission(self, request, view):
        action = {'POST': 'crear', 'PUT': 'editar', 'PATCH': 'editar', 'DELETE': 'eliminar'}.get(request.method, 'listar')
        return granted(request.user, 'horario', action)


def personal_only(user):
    return not es_superadmin(user) and not hasattr(user, 'admin')


def assignments_for(user):
    qs = scoped(AsignacionDocente.objects.all(), user, 'curso__paralelo__grado__unidad_educativa_id')
    if personal_only(user):
        qs = qs.filter(profesor_id=user.profesor.pk) if hasattr(user, 'profesor') else qs.none()
    return qs.select_related('profesor__usuario', 'curso__paralelo__grado__unidad_educativa',
                             'materia_curso__materia', 'calendario_academico')


def schedules_for(user):
    qs = scoped(HorarioClase.objects.filter(estado='ACTIVO'), user, 'curso__paralelo__grado__unidad_educativa_id')
    if personal_only(user):
        qs = qs.filter(profesor_id=user.profesor.pk) if hasattr(user, 'profesor') else qs.none()
    return qs.select_related('bloque_horario', 'profesor__usuario', 'curso__paralelo__grado__unidad_educativa',
                             'asignacion_docente__materia_curso__materia', 'asignacion_docente__calendario_academico', 'aula')


def active_assignments(user):
    return assignments_for(user).filter(tipo='MATERIA', estado='ACTIVO', eliminado_at__isnull=True,
        calendario_academico__activo=True, profesor__estado=True,
        curso__paralelo__grado__unidad_educativa__estado='ACTIVO')


def rooms_for(user):
    qs = Aula.objects.filter(
        estado=True,
        eliminado_at__isnull=True,
        modulo__estado=Modulo.Estado.ACTIVO,
        modulo__eliminado_at__isnull=True,
        modulo__unidad_educativa__isnull=False,
    )
    qs = scoped(qs, user, 'modulo__unidad_educativa_id')
    if personal_only(user):
        profesor = getattr(user, 'profesor', None)
        qs = qs.filter(horarios_clase__profesor=profesor).distinct() if profesor else qs.none()
    return qs.select_related('modulo__unidad_educativa__colegio')


def occurs(day, start, end):
    """Inclusive dates; adjacent time intervals are handled separately."""
    return start.toordinal() + (day - start.isoweekday()) % 7 <= end.toordinal()


class HorarioInput(serializers.Serializer):
    asignacion_docente = serializers.PrimaryKeyRelatedField(queryset=AsignacionDocente.objects.none())
    aula = serializers.PrimaryKeyRelatedField(queryset=Aula.objects.none())
    dia = serializers.IntegerField(min_value=1, max_value=7)
    hora_inicio = serializers.TimeField()
    hora_fin = serializers.TimeField()
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context['request'].user
        self.fields['asignacion_docente'].queryset = active_assignments(user)
        self.fields['aula'].queryset = rooms_for(user)


class HorarioOutput(serializers.ModelSerializer):
    dia = serializers.IntegerField(source='bloque_horario.dia')
    hora_inicio = serializers.TimeField(source='bloque_horario.hora_inicio')
    hora_fin = serializers.TimeField(source='bloque_horario.hora_fin')
    profesor_nombre = serializers.CharField(source='profesor.usuario.get_full_name')
    curso_nombre = serializers.CharField(source='curso.nombre')
    materia_nombre = serializers.CharField(source='asignacion_docente.materia_curso.materia.nombre', default='')
    aula_nombre = serializers.CharField(source='aula.nombre')
    unidad_educativa = serializers.IntegerField(source='curso.paralelo.grado.unidad_educativa_id')
    colegio = serializers.IntegerField(source='curso.paralelo.grado.unidad_educativa.colegio_id')
    gestion = serializers.IntegerField(source='asignacion_docente.calendario_academico.año', allow_null=True, default=None)

    class Meta:
        model = HorarioClase
        fields = ['id', 'asignacion_docente', 'profesor', 'curso', 'aula', 'dia', 'hora_inicio', 'hora_fin',
                  'fecha_inicio', 'fecha_fin', 'estado', 'profesor_nombre', 'curso_nombre',
                  'materia_nombre', 'aula_nombre', 'unidad_educativa', 'colegio', 'gestion']


def validate_period(data, old=None):
    assignment, room = data['asignacion_docente'], data['aula']
    unit = assignment.curso.paralelo.grado.unidad_educativa
    calendar = assignment.calendario_academico
    if (assignment.estado != 'ACTIVO' or assignment.eliminado_at or assignment.tipo != 'MATERIA'
            or not calendar or not calendar.activo or not assignment.profesor.estado or unit.estado != 'ACTIVO'):
        raise serializers.ValidationError({'asignacion_docente': 'Seleccione una asignación activa con gestión vigente.'})
    if (assignment.profesor.unidad_id != unit.pk or calendar.unidad_educativa_id != unit.pk
            or assignment.materia_curso.curso_id != assignment.curso_id):
        raise serializers.ValidationError({'asignacion_docente': 'La asignación tiene relaciones institucionales inconsistentes.'})
    if old and old.curso.paralelo.grado.unidad_educativa_id != unit.pk:
        raise serializers.ValidationError({'asignacion_docente': 'No se puede trasladar un horario a otra unidad.'})
    module = room.modulo if room.modulo_id else None
    if (not room.estado or room.eliminado_at is not None or module is None
            or module.estado != Modulo.Estado.ACTIVO or module.eliminado_at is not None
            or module.unidad_educativa_id != unit.pk):
        raise serializers.ValidationError({'aula': 'El aula debe estar activa y pertenecer a la misma unidad de la asignación.'})
    if data['hora_fin'] <= data['hora_inicio']:
        raise serializers.ValidationError({'hora_fin': 'Debe ser posterior a la hora inicial.'})
    start, end = data['fecha_inicio'], data['fecha_fin']
    if end is None:
        raise serializers.ValidationError({'fecha_fin': 'Indique una fecha final para editar este horario heredado.'})
    lower = max(assignment.fecha_inicio, calendar.fecha_inicio)
    upper = min(assignment.fecha_fin or calendar.fecha_fin, calendar.fecha_fin)
    if start > end or start < lower or end > upper:
        raise serializers.ValidationError({'fecha_fin': f'La vigencia debe estar entre {lower} y {upper}, con inicio no posterior al fin.'})
    if not occurs(data['dia'], start, end):
        raise serializers.ValidationError({'dia': 'El día seleccionado no ocurre dentro de la vigencia.'})


def check_conflicts(data, old=None):
    assignment = data['asignacion_docente']
    # Do not filter by caller's scope: an occupied shared room must remain occupied.
    candidates = HorarioClase.objects.filter(estado='ACTIVO', bloque_horario__dia=data['dia'],
        bloque_horario__hora_inicio__lt=data['hora_fin'], bloque_horario__hora_fin__gt=data['hora_inicio'],
        fecha_inicio__lte=data['fecha_fin']).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=data['fecha_inicio']))
    candidates = candidates.filter(Q(profesor_id=assignment.profesor_id) | Q(curso_id=assignment.curso_id) | Q(aula_id=data['aula'].pk))
    if old:
        candidates = candidates.exclude(pk=old.pk)
    for row in candidates:
        if not occurs(data['dia'], max(data['fecha_inicio'], row.fecha_inicio), min(data['fecha_fin'], row.fecha_fin or date.max)):
            continue
        if row.profesor_id == assignment.profesor_id:
            raise HorarioConflict('Cruce de docente: ya tiene una clase en ese periodo.')
        if row.curso_id == assignment.curso_id:
            raise HorarioConflict('Cruce de curso y paralelo: ya tienen una materia en ese periodo.')
        raise HorarioConflict('Cruce de aula: ya está ocupada en ese periodo.')


class HorarioViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HorarioPermission]
    pagination_class = SchoolPagination
    serializer_class = HorarioOutput
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = schedules_for(self.request.user)
        if self.action == 'list':
            params = self.request.query_params
            qs = id_filters(qs, params, {'profesor': 'profesor_id', 'curso': 'curso_id', 'gestion': 'asignacion_docente__calendario_academico__año'})
            if params.get('semana'):
                try:
                    ref = date.fromisoformat(params['semana'])
                    monday = ref - timedelta(days=ref.weekday())
                    days = [monday + timedelta(days=i) for i in range(7)]
                except (ValueError, OverflowError):
                    raise serializers.ValidationError({'semana': 'Use una fecha válida YYYY-MM-DD.'})
                conditions = Q(pk__in=[])
                for i, day in enumerate(days, 1):
                    conditions |= Q(bloque_horario__dia=i, fecha_inicio__lte=day) & (Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=day))
                qs = qs.filter(conditions)
        return qs.order_by('bloque_horario__dia', 'bloque_horario__hora_inicio', 'pk')

    def _save(self, request, pk=None):
        old = self.get_object() if pk is not None else None
        incoming = HorarioInput(data=request.data, partial=old is not None, context={'request': request})
        incoming.is_valid(raise_exception=True)
        data = dict(incoming.validated_data)
        if old:
            base = {name: getattr(old, name) for name in ('asignacion_docente', 'aula', 'fecha_inicio', 'fecha_fin')}
            base.update({name: getattr(old.bloque_horario, name) for name in ('dia', 'hora_inicio', 'hora_fin')})
            base.update(data)
            data = base
        unit = data['asignacion_docente'].curso.paralelo.grado.unidad_educativa
        if old and old.curso.paralelo.grado.unidad_educativa_id != unit.pk:
            raise serializers.ValidationError({'asignacion_docente': 'No se puede trasladar un horario a otra unidad.'})
        try:
            with transaction.atomic():
                # One school lock serializes checks and writes, including rooms shared by units.
                Colegio.objects.select_for_update().get(pk=unit.colegio_id)
                if old:
                    old = get_object_or_404(schedules_for(request.user).select_for_update(of=('self',)), pk=old.pk)
                    if old.sesiones.exists():
                        raise HorarioConflict('El horario tiene sesiones de asistencia; conserve su historial y cree otro periodo.')
                    # Merge PATCH against the locked row, never a stale pre-lock snapshot.
                    for name in ('asignacion_docente', 'aula', 'fecha_inicio', 'fecha_fin'):
                        if name not in incoming.validated_data:
                            data[name] = getattr(old, name)
                    for name in ('dia', 'hora_inicio', 'hora_fin'):
                        if name not in incoming.validated_data:
                            data[name] = getattr(old.bloque_horario, name)
                data['asignacion_docente'] = get_object_or_404(assignments_for(request.user).select_for_update(of=('self',)), pk=data['asignacion_docente'].pk)
                data['aula'] = get_object_or_404(rooms_for(request.user).select_for_update(of=('self',)), pk=data['aula'].pk)
                validate_period(data, old)
                check_conflicts(data, old)
                blocks = BloqueHorario.objects.filter(unidad_educativa=unit, turno=unit.turno, dia=data['dia'])
                block = blocks.filter(hora_inicio=data['hora_inicio'], hora_fin=data['hora_fin'], tipo='CLASE', estado='ACTIVO').order_by('pk').first()
                if not block:
                    block = BloqueHorario.objects.create(unidad_educativa=unit, turno=unit.turno, dia=data['dia'],
                        orden=(blocks.aggregate(value=Max('orden'))['value'] or 0) + 1,
                        hora_inicio=data['hora_inicio'], hora_fin=data['hora_fin'])
                assignment = data['asignacion_docente']
                row = old or HorarioClase()
                row.asignacion_docente, row.profesor, row.curso = assignment, assignment.profesor, assignment.curso
                row.aula, row.bloque_horario = data['aula'], block
                row.fecha_inicio, row.fecha_fin = data['fecha_inicio'], data['fecha_fin']
                row.save()
                registrar_evento(accion='ACTUALIZAR' if old else 'CREAR', entidad='HORARIO_CLASE', entidad_id=row.pk,
                    request=request, unidad=unit, cambios={'campos': list(incoming.validated_data)})
                result = HorarioOutput(row).data
        except IntegrityError:
            raise HorarioConflict('Ya existe ese periodo o cambió durante el guardado. Actualice el horario.')
        return Response(result, status=status.HTTP_200_OK if old else status.HTTP_201_CREATED)

    def create(self, request):
        return self._save(request)

    def partial_update(self, request, pk=None):
        return self._save(request, pk)

    def destroy(self, request, pk=None):
        row = self.get_object()
        unit = row.curso.paralelo.grado.unidad_educativa
        try:
            with transaction.atomic():
                Colegio.objects.select_for_update().get(pk=unit.colegio_id)
                row = get_object_or_404(schedules_for(request.user).select_for_update(of=('self',)), pk=row.pk)
                registrar_evento(accion='ELIMINAR', entidad='HORARIO_CLASE', entidad_id=row.pk,
                    request=request, unidad=unit, cambios={'campos': ['horario']})
                row.delete()
        except ProtectedError:
            raise HorarioConflict('El horario tiene sesiones de asistencia; no puede eliminarse.')
        return Response(status=status.HTTP_204_NO_CONTENT)


class HorarioCatalogViewSet(viewsets.GenericViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HorarioPermission]
    pagination_class = SchoolPagination
    http_method_names = ['get', 'head', 'options']
    kind = 'asignaciones'

    def list(self, request):
        params = request.query_params
        search = params.get('search', '').strip()
        # Filter options must also cover historical schedules after a calendar closes.
        assignments = assignments_for(request.user)
        if self.kind == 'asignaciones':
            qs = id_filters(active_assignments(request.user), params, {'profesor': 'profesor_id', 'curso': 'curso_id', 'gestion': 'calendario_academico__año'})
            if search:
                qs = qs.filter(Q(profesor__usuario__nombre__icontains=search) | Q(profesor__usuario__apellido__icontains=search)
                    | Q(curso__nombre__icontains=search) | Q(materia_curso__materia__nombre__icontains=search))
        elif self.kind == 'aulas':
            qs = id_filters(rooms_for(request.user), params, {
                'colegio': 'modulo__unidad_educativa__colegio_id',
                'unidad_educativa': 'modulo__unidad_educativa_id',
            })
            assignment_id = params.get('asignacion_docente')
            if assignment_id is not None:
                try:
                    assignment_id = int(assignment_id)
                except (TypeError, ValueError):
                    raise serializers.ValidationError({'asignacion_docente': 'Debe ser un entero positivo.'})
                if assignment_id <= 0:
                    raise serializers.ValidationError({'asignacion_docente': 'Debe ser un entero positivo.'})
                assignment = assignments.filter(pk=assignment_id).first()
                if assignment is None:
                    qs = qs.none()
                else:
                    assignment_unit = assignment.curso.paralelo.grado.unidad_educativa_id
                    unit_param = params.get('unidad_educativa')
                    if unit_param is not None and int(unit_param) != assignment_unit:
                        raise serializers.ValidationError({'unidad_educativa': 'Debe coincidir con la unidad de la asignación docente.'})
                    qs = qs.filter(modulo__unidad_educativa_id=assignment_unit)
            if search:
                qs = qs.filter(Q(nombre__icontains=search) | Q(modulo__nombre__icontains=search))
        elif self.kind == 'cursos':
            qs = Curso.objects.filter(pk__in=assignments.values('curso_id'))
            if search:
                qs = qs.filter(Q(nombre__icontains=search) | Q(paralelo__letra__icontains=search))
        else:
            qs = Profesor.objects.filter(pk__in=assignments.values('profesor_id')).select_related('usuario')
            if search:
                qs = qs.filter(Q(usuario__nombre__icontains=search) | Q(usuario__apellido__icontains=search))
        page = self.paginate_queryset(qs.order_by('pk'))
        return self.get_paginated_response([self.item(row) for row in page])

    def item(self, row):
        if self.kind == 'asignaciones':
            calendar = row.calendario_academico
            unit = row.curso.paralelo.grado.unidad_educativa
            return {'id': row.pk, 'nombre': f'{row.materia_curso.materia.nombre} · {row.curso.nombre} · {full_name(row.profesor.usuario)} · {calendar.año}',
                'profesor': row.profesor_id, 'curso': row.curso_id, 'unidad_educativa': unit.pk,
                'colegio': unit.colegio_id, 'gestion': calendar.año,
                'fecha_inicio': max(row.fecha_inicio, calendar.fecha_inicio).isoformat(),
                'fecha_fin': min(row.fecha_fin or calendar.fecha_fin, calendar.fecha_fin).isoformat()}
        if self.kind == 'aulas':
            return {
                'id': row.pk,
                'nombre': f'{row.nombre} · {row.modulo.nombre}',
                'colegio': row.modulo.unidad_educativa.colegio_id,
                'unidad_educativa': row.modulo.unidad_educativa_id,
            }
        return {'id': row.pk, 'nombre': full_name(row.usuario) if self.kind == 'profesores' else f'{row.nombre} · {row.paralelo}'}


class HorarioAsignacionViewSet(HorarioCatalogViewSet):
    kind = 'asignaciones'


class HorarioAulaViewSet(HorarioCatalogViewSet):
    kind = 'aulas'


class HorarioCursoViewSet(HorarioCatalogViewSet):
    kind = 'cursos'


class HorarioProfesorViewSet(HorarioCatalogViewSet):
    kind = 'profesores'

from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import RegistroAsistencia, DetalleAsistencia
from .serializers import (
    RegistroAsistenciaSerializer,
    DetalleAsistenciaSerializer,
    RegistrarAsistenciaSerializer,
    EstudianteAsistenciaSerializer,
    ResumenAsistenciaSerializer,
)
from aplicaciones.usuarios.permissions import IsProfesor
from aplicaciones.usuarios.tenancy import es_superadmin, unidad_id_usuario
from aplicaciones.academico.models import Curso, MateriaCurso
from aplicaciones.estudiantes.models import Estudiante

_ROLES_GESTION = {
    'admin', 'director', 'regente', 'secretaria', 'secretario',
    'auxiliar', 'auxiliar de docencia', 'administrativo',
}


def _es_gestion(user):
    """Roles con permiso de gestion de asistencia en cualquier curso.

    Reconoce perfil `admin`/`superadmin` y, ademas, el nombre del rol
    (mismo criterio que `_IsRolNombre` en usuarios/permissions.py), de modo
    que un regente o secretaria con rol `Admin` tambien pueda gestionar.
    """
    if not getattr(user, 'is_authenticated', False):
        return False
    if es_superadmin(user) or hasattr(user, 'admin'):
        return True
    nombre = str(getattr(getattr(user, 'rol', None), 'nombre', '')).strip().lower()
    return nombre in _ROLES_GESTION


def _misma_unidad(user, unidad_id):
    """True si el usuario pertenece a la unidad indicada (SuperAdmin: siempre)."""
    if es_superadmin(user):
        return True
    uid = unidad_id_usuario(user)
    return uid is not None and uid == unidad_id


class _EsGestion(permissions.BasePermission):
    """Solo para administrativos / direccion / regencia (por nombre de rol o perfil)."""

    message = 'No tiene permiso para gestionar asistencia.'

    def has_permission(self, request, view):
        return _es_gestion(request.user)


_ESCRITURA = (_EsGestion | IsProfesor)


def _puede_operar_asignacion(user, asignacion):
    """Un docente solo opera las asignaciones que dicta o de los cursos que tutorea."""
    if es_superadmin(user):
        return True
    if _es_gestion(user):
        return _misma_unidad(user, asignacion.curso.paralelo.grado.unidad_educativa_id)
    if hasattr(user, 'profesor'):
        prof = user.profesor
        return asignacion.profesor_id == prof.pk or asignacion.curso.tutor_id == prof.pk
    return False


def _puede_operar_curso(user, curso):
    if es_superadmin(user):
        return True
    if _es_gestion(user):
        return _misma_unidad(user, curso.paralelo.grado.unidad_educativa_id)
    if hasattr(user, 'profesor'):
        prof = user.profesor
        return curso.tutor_id == prof.pk or MateriaCurso.objects.filter(
            curso=curso, profesor=prof,
        ).exists()
    return False


def _alcance_lectura_registro(user):
    """Restringe los RegistroAsistencia visibles por rol.

    Devuelve None si no hay restriccion (superadmin/gestion); si no, un Q
    que acota a lo que ese usuario puede ver. Sin esto, cualquier
    autenticado podia leer la asistencia de cualquier estudiante pasando
    un ``estudiante``/``curso`` arbitrario por query param.

    Tutor/estudiante quedan en Q(pk__in=[]) a proposito: el serializer de
    RegistroAsistencia anida el detalle de TODOS los estudiantes de esa
    clase ese dia (ver RegistroAsistenciaSerializer.detalles, sin filtrar),
    asi que aunque se acotara que registros ven, seguirian viendo a sus
    companeros de curso. Deben consultar DetalleAsistencia en su lugar,
    que si esta acotado fila por fila.
    """
    if es_superadmin(user) or _es_gestion(user):
        return None
    if hasattr(user, 'profesor'):
        prof = user.profesor
        return Q(asignacion__profesor=prof) | Q(asignacion__curso__tutor=prof)
    return Q(pk__in=[])


def _alcance_lectura_detalle(user):
    """Equivalente a `_alcance_lectura_registro` para DetalleAsistencia."""
    if es_superadmin(user) or _es_gestion(user):
        return None
    if hasattr(user, 'profesor'):
        prof = user.profesor
        return Q(registro__asignacion__profesor=prof) | Q(registro__asignacion__curso__tutor=prof)
    if hasattr(user, 'tutor'):
        return Q(estudiante__tutores__tutor__usuario=user)
    if hasattr(user, 'estudiante'):
        return Q(estudiante__usuario=user)
    return Q(pk__in=[])


def _filtros_registro(request):
    """Aplica los filtros de consulta sobre los registros de asistencia."""
    qs = RegistroAsistencia.objects.select_related(
        'asignacion__curso', 'asignacion__materia', 'periodo', 'docente',
    )
    alcance = _alcance_lectura_registro(request.user)
    if alcance is not None:
        qs = qs.filter(alcance).distinct()
    p = request.query_params
    if p.get('curso'):
        qs = qs.filter(asignacion__curso_id=p['curso'])
    if p.get('asignacion'):
        qs = qs.filter(asignacion_id=p['asignacion'])
    if p.get('periodo'):
        qs = qs.filter(periodo_id=p['periodo'])
    if p.get('fecha'):
        qs = qs.filter(fecha=p['fecha'])
    if p.get('desde'):
        qs = qs.filter(fecha__gte=p['desde'])
    if p.get('hasta'):
        qs = qs.filter(fecha__lte=p['hasta'])
    if p.get('estudiante'):
        qs = qs.filter(detalles__estudiante_id=p['estudiante']).distinct()
    return qs


class RegistroAsistenciaViewSet(viewsets.ModelViewSet):
    serializer_class = RegistroAsistenciaSerializer

    def get_queryset(self):
        return _filtros_registro(self.request)

    def get_permissions(self):
        # 'estudiantes' expone el listado completo de un curso (para marcar
        # asistencia), no es una consulta de autoservicio: solo gestion/profesor.
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'registrar', 'estudiantes']:
            return [permissions.IsAuthenticated(), _ESCRITURA()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(docente=self.request.user)

    @action(detail=False, methods=['get'], url_path='estudiantes')
    def estudiantes(self, request):
        """Lista los estudiantes inscritos en la asignación/curso para registrar.

        Parámetros: ``asignacion`` o ``curso`` y opcionalmente ``fecha``.
        Devuelve cada estudiante con su estado de asistencia ya registrado (si existe).
        """
        p = request.query_params
        asignacion_id = p.get('asignacion')
        curso_id = p.get('curso')
        fecha = p.get('fecha')

        if asignacion_id:
            asignacion = MateriaCurso.objects.select_related('curso').filter(
                pk=asignacion_id,
            ).first()
            if not asignacion:
                return Response(
                    {'detail': 'Asignación no encontrada.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not _puede_operar_asignacion(request.user, asignacion):
                return Response(
                    {'detail': 'No tiene permiso para registrar asistencia en esta asignación.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            estudiantes = Estudiante.objects.filter(
                curso=asignacion.curso, estado=True,
            ).select_related('usuario').distinct()
        elif curso_id:
            curso = Curso.objects.filter(pk=curso_id).first()
            if not curso:
                return Response(
                    {'detail': 'Curso no encontrado.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not _puede_operar_curso(request.user, curso):
                return Response(
                    {'detail': 'No tiene permiso para registrar asistencia en este curso.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            estudiantes = Estudiante.objects.filter(
                curso_id=curso_id, estado=True,
            ).select_related('usuario').distinct()
        else:
            return Response(
                {'detail': 'Debe indicar asignacion o curso.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existentes = {}
        if asignacion_id and fecha:
            registro = RegistroAsistencia.objects.filter(
                asignacion_id=asignacion_id, fecha=fecha,
            ).first()
            if registro:
                existentes = {
                    d.estudiante_id: d
                    for d in registro.detalles.all()
                }

        data = []
        for est in estudiantes:
            det = existentes.get(est.pk)
            data.append({
                'estudiante': est.pk,
                'nombre': est.usuario.nombre,
                'apellido': est.usuario.apellido,
                'rude': est.rude,
                'estado': det.estado if det else None,
                'observacion': det.observacion if det else '',
            })
        return Response(EstudianteAsistenciaSerializer(data, many=True).data)

    @action(detail=False, methods=['post'], url_path='registrar')
    def registrar(self, request):
        """Registra la asistencia completa (cabecera + detalles) de una fecha.

        Evita duplicados: reutiliza el registro existente de (fecha, asignación)
        y actualiza o crea cada detalle por estudiante.
        """
        serializer = RegistrarAsistenciaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        asignacion = data['asignacion']

        if not _puede_operar_asignacion(request.user, asignacion):
            raise PermissionDenied(
                'No tiene permiso para registrar asistencia en esta asignación.'
            )

        est_ids = [d['estudiante'].pk for d in data['detalles']]
        inscritos = set(
            Estudiante.objects.filter(
                pk__in=est_ids, curso=asignacion.curso, estado=True,
            ).values_list('pk', flat=True)
        )
        no_inscritos = sorted(set(est_ids) - inscritos)
        if no_inscritos:
            raise ValidationError({
                'detalles': (
                    'Estudiantes no inscritos (o sin inscripción activa) en el curso '
                    f'de la asignación: {no_inscritos}.'
                ),
            })

        with transaction.atomic():
            registro, _ = RegistroAsistencia.objects.get_or_create(
                fecha=data['fecha'],
                asignacion=data['asignacion'],
                defaults={
                    'docente': request.user,
                    'periodo': data.get('periodo'),
                    'observacion': data.get('observacion', ''),
                },
            )
            registro.periodo = data.get('periodo', registro.periodo)
            if 'observacion' in data:
                registro.observacion = data['observacion']
            registro.docente = registro.docente or request.user
            registro.save()

            for d in data['detalles']:
                DetalleAsistencia.objects.update_or_create(
                    registro=registro,
                    estudiante=d['estudiante'],
                    defaults={
                        'estado': d['estado'],
                        'observacion': d.get('observacion', ''),
                    },
                )

        return Response(
            RegistroAsistenciaSerializer(registro).data,
            status=status.HTTP_201_CREATED,
        )


class DetalleAsistenciaViewSet(viewsets.ModelViewSet):
    serializer_class = DetalleAsistenciaSerializer

    def get_queryset(self):
        qs = DetalleAsistencia.objects.select_related(
            'registro__asignacion__curso', 'registro__asignacion__materia',
            'estudiante__usuario',
        )
        alcance = _alcance_lectura_detalle(self.request.user)
        if alcance is not None:
            qs = qs.filter(alcance).distinct()
        p = self.request.query_params
        if p.get('estudiante'):
            qs = qs.filter(estudiante_id=p['estudiante'])
        if p.get('registro'):
            qs = qs.filter(registro_id=p['registro'])
        if p.get('curso'):
            qs = qs.filter(registro__asignacion__curso_id=p['curso'])
        if p.get('asignacion'):
            qs = qs.filter(registro__asignacion_id=p['asignacion'])
        if p.get('periodo'):
            qs = qs.filter(registro__periodo_id=p['periodo'])
        if p.get('estado'):
            qs = qs.filter(estado=p['estado'])
        if p.get('desde'):
            qs = qs.filter(registro__fecha__gte=p['desde'])
        if p.get('hasta'):
            qs = qs.filter(registro__fecha__lte=p['hasta'])
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), _ESCRITURA()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='resumen')
    def resumen(self, request):
        """Resumen de asistencia por estudiante (o de todo un curso).

        Parámetros: ``estudiante`` o ``curso``; opcional ``periodo``/``desde``/``hasta``.
        """
        qs = self.get_queryset()
        p = request.query_params

        estudiantes = {}
        for det in qs:
            est = det.estudiante
            acc = estudiantes.setdefault(est.pk, {
                'estudiante': est.pk,
                'nombre': est.usuario.nombre,
                'apellido': est.usuario.apellido,
                'curso': str(est.curso) if est.curso else None,
                'total': 0, 'presentes': 0, 'ausentes': 0, 'tardes': 0, 'licencias': 0,
            })
            acc['total'] += 1
            if det.estado == 'P':
                acc['presentes'] += 1
            elif det.estado == 'A':
                acc['ausentes'] += 1
            elif det.estado == 'T':
                acc['tardes'] += 1
            elif det.estado == 'L':
                acc['licencias'] += 1

        resultados = []
        for acc in estudiantes.values():
            total = acc['total']
            asistio = acc['presentes'] + acc['licencias'] + Decimal('0.5') * acc['tardes']
            faltas = total - asistio
            acc['porcentaje_asistencia'] = round(Decimal(asistio) / total * 100, 2) if total else Decimal('0.00')
            acc['porcentaje_faltas'] = round(Decimal(faltas) / total * 100, 2) if total else Decimal('0.00')
            resultados.append(acc)

        if p.get('estudiante'):
            resultados = [r for r in resultados if r['estudiante'] == int(p['estudiante'])]

        return Response(ResumenAsistenciaSerializer(resultados, many=True).data)

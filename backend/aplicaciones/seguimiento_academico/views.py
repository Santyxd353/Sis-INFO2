from decimal import Decimal

from django.db.models import Q
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import (
    HistorialEstudiante, Nota, RiesgoAcademico, ConfiguracionRiesgo,
)
from .serializers import (
    HistorialEstudianteSerializer, NotaSerializer, RiesgoAcademicoSerializer,
    ConfiguracionRiesgoSerializer, AlertaSerializer,
)
from aplicaciones.usuarios.permissions import (
    IsAdmin, IsSuperAdmin, IsProfesor, IsDirector, IsSecretaria,
)
from aplicaciones.usuarios.tenancy import es_superadmin, unidad_id_usuario
from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.asistencia.models import DetalleAsistencia

_ESCRITURA = (IsSuperAdmin | IsAdmin | IsProfesor | IsDirector | IsSecretaria)

_NIVEL_ORDEN = {None: 0, 'B': 1, 'M': 2, 'A': 3}
_NIVEL_DISPLAY = {'B': 'Bajo', 'M': 'Medio', 'A': 'Alto'}

_ROLES_GESTION = {
    'admin', 'director', 'regente', 'secretaria', 'secretario',
    'auxiliar', 'auxiliar de docencia', 'administrativo',
}


def _es_gestion(user):
    """Roles con gestión de seguimiento académico (administrativos/dirección)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if es_superadmin(user) or hasattr(user, 'admin'):
        return True
    nombre = str(getattr(getattr(user, 'rol', None), 'nombre', '')).strip().lower()
    return nombre in _ROLES_GESTION


def _escalar(nivel_actual, nuevo):
    return nuevo if _NIVEL_ORDEN[nuevo] > _NIVEL_ORDEN[nivel_actual] else nivel_actual


def _promedio_estudiante(estudiante, periodo=None):
    notas = Nota.objects.filter(historial__estudiante=estudiante)
    if periodo:
        notas = notas.filter(historial__periodo_id=periodo)
    if notas.exists():
        total_p = sum(n.ponderacion for n in notas) or Decimal('1')
        return round(sum(n.nota * n.ponderacion for n in notas) / total_p, 2)
    h = HistorialEstudiante.objects.filter(estudiante=estudiante)
    if periodo:
        h = h.filter(periodo_id=periodo)
    h = h.order_by('-periodo__fecha_inicio').first()
    return h.promedio if h else None


def _resumen_asistencia(estudiante, periodo=None, desde=None, hasta=None):
    qs = DetalleAsistencia.objects.filter(estudiante=estudiante)
    if periodo:
        qs = qs.filter(registro__periodo_id=periodo)
    if desde:
        qs = qs.filter(registro__fecha__gte=desde)
    if hasta:
        qs = qs.filter(registro__fecha__lte=hasta)
    total = qs.count()
    presentes = qs.filter(estado='P').count()
    ausentes = qs.filter(estado='A').count()
    tardes = qs.filter(estado='T').count()
    licencias = qs.filter(estado='L').count()
    if total:
        asistio = Decimal(presentes) + Decimal(licencias) + Decimal('0.5') * Decimal(tardes)
        porcentaje_faltas = round((Decimal(total) - asistio) / Decimal(total) * 100, 2)
    else:
        porcentaje_faltas = Decimal('0.00')
    return {
        'total': total, 'presentes': presentes, 'ausentes': ausentes,
        'tardes': tardes, 'licencias': licencias,
        'porcentaje_faltas': porcentaje_faltas,
    }


def _analizar_riesgo(estudiante, config, periodo=None):
    promedio = _promedio_estudiante(estudiante, periodo)
    asist = _resumen_asistencia(estudiante, periodo)
    faltas = asist['porcentaje_faltas']

    tipos, motivos = [], []
    nivel = None

    if promedio is not None and promedio < config.umbral_rendimiento:
        tipos.append('rendimiento')
        motivos.append(
            f'Bajo rendimiento: promedio {promedio} inferior al umbral {config.umbral_rendimiento}.'
        )
        nivel = _escalar(nivel, 'A' if promedio < config.umbral_riesgo_alto else 'M')

    if faltas >= config.umbral_inasistencia:
        tipos.append('inasistencia')
        motivos.append(
            f'Inasistencia recurrente: {faltas}% de faltas supera el umbral {config.umbral_inasistencia}%.'
        )
        nivel = _escalar(nivel, 'A')

    return {
        'estudiante': estudiante.pk,
        'nombre': estudiante.usuario.nombre,
        'apellido': estudiante.usuario.apellido,
        'curso': str(estudiante.curso) if estudiante.curso else None,
        'promedio': promedio,
        'porcentaje_faltas': faltas,
        'nivel': nivel,
        'nivel_display': _NIVEL_DISPLAY.get(nivel),
        'tipos': tipos,
        'motivos': motivos,
        'umbral_rendimiento': config.umbral_rendimiento,
        'umbral_inasistencia': config.umbral_inasistencia,
    }


def _estudiantes_en_alcance(user, curso_id=None):
    """Estudiantes que el usuario puede consultar según su rol y unidad educativa.

    SuperAdmin: todos. Gestión (dirección/secretaría/afines): su unidad.
    Docente: los de los cursos que tutorea o dicta. Tutor: sus representados.
    Estudiante: solo su propio registro. Otros: ninguno.
    """
    qs = Estudiante.objects.select_related('usuario', 'curso').all()
    if curso_id:
        qs = qs.filter(curso_id=curso_id)
    if es_superadmin(user):
        return qs
    if _es_gestion(user):
        uid = unidad_id_usuario(user)
        return qs.filter(unidad_id=uid) if uid else qs.none()
    if hasattr(user, 'estudiante'):
        return qs.filter(pk=user.estudiante.pk)
    if hasattr(user, 'tutor'):
        return qs.filter(tutores__tutor__usuario=user).distinct()
    if hasattr(user, 'profesor'):
        prof = user.profesor
        return qs.filter(
            Q(curso__tutor=prof) | Q(curso__materias__profesor=prof)
        ).distinct()
    return qs.none()


def _validar_estudiante(user, estudiante_id):
    """Deniega la escritura si el estudiante no está en el alcance del usuario."""
    if not _estudiantes_en_alcance(user).filter(pk=estudiante_id).exists():
        raise PermissionDenied('No tiene acceso a los datos de ese estudiante.')


class HistorialEstudianteViewSet(viewsets.ModelViewSet):
    serializer_class = HistorialEstudianteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = HistorialEstudiante.objects.select_related(
            'estudiante__usuario', 'periodo__calendario', 'curso',
        ).filter(estudiante__in=_estudiantes_en_alcance(self.request.user))
        p = self.request.query_params
        if p.get('estudiante'):
            qs = qs.filter(estudiante_id=p['estudiante'])
        if p.get('periodo'):
            qs = qs.filter(periodo_id=p['periodo'])
        if p.get('gestion'):
            qs = qs.filter(periodo__calendario__año=p['gestion'])
        if p.get('curso'):
            qs = qs.filter(curso_id=p['curso'])
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), (IsSuperAdmin | IsAdmin | IsDirector | IsSecretaria)()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        _validar_estudiante(self.request.user, serializer.validated_data['estudiante'].pk)
        serializer.save()

    def perform_update(self, serializer):
        estudiante = serializer.validated_data.get('estudiante', serializer.instance.estudiante)
        _validar_estudiante(self.request.user, estudiante.pk)
        serializer.save()


class NotaViewSet(viewsets.ModelViewSet):
    serializer_class = NotaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Nota.objects.select_related(
            'historial__estudiante', 'materia',
        ).filter(historial__estudiante__in=_estudiantes_en_alcance(self.request.user))
        p = self.request.query_params
        if p.get('historial'):
            qs = qs.filter(historial_id=p['historial'])
        if p.get('estudiante'):
            qs = qs.filter(historial__estudiante_id=p['estudiante'])
        if p.get('gestion'):
            qs = qs.filter(historial__periodo__calendario__año=p['gestion'])
        if p.get('periodo'):
            qs = qs.filter(historial__periodo_id=p['periodo'])
        if p.get('materia'):
            qs = qs.filter(materia_id=p['materia'])
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), _ESCRITURA()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        _validar_estudiante(self.request.user, serializer.validated_data['historial'].estudiante_id)
        serializer.save()

    def perform_update(self, serializer):
        historial = serializer.validated_data.get('historial', serializer.instance.historial)
        _validar_estudiante(self.request.user, historial.estudiante_id)
        serializer.save()


class RiesgoAcademicoViewSet(viewsets.ModelViewSet):
    serializer_class = RiesgoAcademicoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = RiesgoAcademico.objects.select_related(
            'estudiante__usuario', 'periodo', 'responsable',
        ).filter(estudiante__in=_estudiantes_en_alcance(self.request.user))
        p = self.request.query_params
        if p.get('estudiante'):
            qs = qs.filter(estudiante_id=p['estudiante'])
        if p.get('nivel'):
            qs = qs.filter(nivel=p['nivel'])
        if p.get('periodo'):
            qs = qs.filter(periodo_id=p['periodo'])
        if p.get('curso'):
            qs = qs.filter(estudiante__curso_id=p['curso'])
        if p.get('activo') is not None:
            activo = p['activo'].lower() in ('1', 'true', 'si', 'sí')
            qs = qs.filter(activo=activo)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [permissions.IsAuthenticated(), _ESCRITURA()]
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), (IsSuperAdmin | IsAdmin | IsDirector)()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        _validar_estudiante(self.request.user, serializer.validated_data['estudiante'].pk)
        serializer.save(responsable=self.request.user)

    def perform_update(self, serializer):
        estudiante = serializer.validated_data.get('estudiante', serializer.instance.estudiante)
        _validar_estudiante(self.request.user, estudiante.pk)
        serializer.save()


class ConfiguracionRiesgoViewSet(viewsets.ModelViewSet):
    """Umbrales configurables de rendimiento e inasistencia."""
    serializer_class = ConfiguracionRiesgoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ConfiguracionRiesgo.objects.all()
        if not es_superadmin(self.request.user):
            uid = unidad_id_usuario(self.request.user)
            qs = qs.filter(Q(unidad__isnull=True) | Q(unidad_id=uid))
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), (IsSuperAdmin | IsAdmin | IsDirector)()]
        return [permissions.IsAuthenticated()]

    def _validar_unidad(self, usuario, unidad):
        if es_superadmin(usuario) or unidad is None:
            return
        uid = unidad_id_usuario(usuario)
        if not uid or unidad.pk != uid:
            raise PermissionDenied('No puede configurar umbrales de otra unidad educativa.')

    def perform_create(self, serializer):
        self._validar_unidad(self.request.user, serializer.validated_data.get('unidad'))
        serializer.save()

    def perform_update(self, serializer):
        unidad = serializer.validated_data.get('unidad', serializer.instance.unidad)
        self._validar_unidad(self.request.user, unidad)
        serializer.save()


class AlertaViewSet(viewsets.ViewSet):
    """Identificación y detalle de alertas de riesgo académico / inasistencia."""
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        p = request.query_params
        config = ConfiguracionRiesgo.get_config(unidad_id_usuario(request.user))
        estudiantes = _estudiantes_en_alcance(request.user, p.get('curso'))

        resultados = [
            _analizar_riesgo(est, config, p.get('periodo'))
            for est in estudiantes
        ]

        nivel_f = p.get('nivel')
        tipo_f = p.get('tipo')
        if not p.get('incluir_sin'):
            resultados = [r for r in resultados if r['nivel']]
        if nivel_f and nivel_f.upper() != 'TODOS':
            resultados = [r for r in resultados if r['nivel'] == nivel_f.upper()]
        if tipo_f and tipo_f != 'todos':
            resultados = [r for r in resultados if tipo_f in r['tipos']]

        return Response(AlertaSerializer(resultados, many=True).data)

    def retrieve(self, request, pk=None):
        config = ConfiguracionRiesgo.get_config(unidad_id_usuario(request.user))
        estudiante = _estudiantes_en_alcance(request.user).select_related(
            'usuario', 'curso',
        ).filter(pk=pk).first()
        if not estudiante:
            return Response({'detail': 'Estudiante no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        p = request.query_params
        alerta = _analizar_riesgo(estudiante, config, p.get('periodo'))
        alerta['asistencia'] = _resumen_asistencia(
            estudiante, p.get('periodo'), p.get('desde'), p.get('hasta'),
        )
        alerta['notas'] = NotaSerializer(
            Nota.objects.filter(historial__estudiante=estudiante).select_related('materia', 'historial__periodo'),
            many=True,
        ).data
        return Response(alerta)

    @action(detail=False, methods=['post'], url_path='recalcular')
    def recalcular(self, request):
        """Persiste/actualiza los registros de RiesgoAcademico según los umbrales."""
        periodo = request.data.get('periodo') or request.query_params.get('periodo')
        if not periodo:
            return Response({'detail': 'Se requiere el periodo.'}, status=status.HTTP_400_BAD_REQUEST)

        config = ConfiguracionRiesgo.get_config(unidad_id_usuario(request.user))
        estudiantes = _estudiantes_en_alcance(request.user, request.query_params.get('curso'))

        creados = 0
        for est in estudiantes:
            alerta = _analizar_riesgo(est, config, periodo)
            if not alerta['nivel']:
                RiesgoAcademico.objects.filter(
                    estudiante=est, periodo_id=periodo, activo=True,
                ).update(activo=False)
                continue
            RiesgoAcademico.objects.update_or_create(
                estudiante=est, periodo_id=periodo, activo=True,
                defaults={
                    'nivel': alerta['nivel'],
                    'motivo': ' '.join(alerta['motivos']),
                    'responsable': request.user,
                },
            )
            creados += 1
        return Response({'procesados': creados})

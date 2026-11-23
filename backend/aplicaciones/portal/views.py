from django.db.models import Avg, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from aplicaciones.academico.models import Curso
from aplicaciones.comunicacion.models import Comunicado, DestinatarioComunicado
from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.estudiantes.alcance_familiar import family_students
from aplicaciones.institucion.models import UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.feature_access import granted
from aplicaciones.usuarios.tenancy import es_superadmin, normalizar_nombre, resolver_alcance
from .servicios import (attendance, attendance_queries, calendar_context, coherent_students,
    communications, documents, enrollment_for, notes, positive, schedules, student_row, valid_results)


class PortalAPIView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'head', 'options']

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response

    def require_active(self, user):
        if (not user.estado or not user.is_active or not user.rol_id or not user.rol.activo
                or es_superadmin(user)):
            raise PermissionDenied('El perfil no está habilitado para este portal.')


class FamiliaView(PortalAPIView):
    def get(self, request):
        user = request.user
        self.require_active(user)
        students = family_students(user)
        student_id = positive(request.query_params, 'estudiante')
        calendar_id = positive(request.query_params, 'calendario_academico')
        period_id = positive(request.query_params, 'periodo')
        students = students.select_related('usuario', 'unidad', 'curso').order_by('usuario__nombre', 'usuario__apellido', 'pk').distinct()
        student = get_object_or_404(students, pk=student_id) if student_id else students.first()
        calendars, selected_calendar, periods, calendar, period = calendar_context(
            student.unidad_id if student else None, calendar_id, period_id)
        enrollment = enrollment_for(student, calendar) if student else None
        messages, inbox = communications(user) if student else ([], {'no_leidas': 0, 'recientes': []})
        return Response({'estudiantes': [student_row(s) for s in students],
            'seleccionado': student.pk if student else None,
            'estudiante': student_row(student, enrollment) if student else None,
            'gestiones': calendars, 'gestion': selected_calendar, 'periodos': periods,
            'periodo': period.pk if period else None, 'notas': notes(enrollment, calendar, period),
            'horarios': schedules(enrollment, calendar),
            'asistencia': attendance(enrollment, calendar, period, student),
            'boletines': documents(enrollment, calendar, period), 'comunicados': messages,
            'notificaciones': inbox,
            'pagos': {'disponible': False, 'mensaje': 'La consulta de pagos familiares aún no está disponible en el sistema.'},
            'actualizado_at': timezone.now()})


class PanelDirectorView(PortalAPIView):
    def get(self, request):
        user = request.user
        self.require_active(user)
        admin = getattr(user, 'admin', None)
        if (not admin or not admin.estado or normalizar_nombre(user.rol.nombre) != 'admin'
                or normalizar_nombre(getattr(admin.puesto, 'nombre', '')) != 'director'):
            raise PermissionDenied('Se requiere un director institucional.')
        scope = resolver_alcance(user)
        if scope['tipo'] != 'COLEGIO' or not granted(user, 'portal-panel', 'listar'):
            raise PermissionDenied('Se requiere permiso para consultar el panel institucional.')
        unit_id = positive(request.query_params, 'unidad_educativa')
        calendar_id = positive(request.query_params, 'calendario_academico')
        period_id = positive(request.query_params, 'periodo')
        units = UnidadEducativa.objects.filter(colegio_id=scope['colegio_id']).order_by('nombre', 'pk')
        unit = get_object_or_404(units, pk=unit_id) if unit_id else None
        if not unit and (calendar_id or period_id):
            raise ValidationError('Seleccione una unidad educativa para filtrar la gestión o el periodo.')
        calendars, selected_calendar, periods, calendar, period = calendar_context(unit.pk if unit else None, calendar_id, period_id)
        unit_ids = [unit.pk] if unit else list(units.values_list('pk', flat=True))
        students = coherent_students(Estudiante.objects.filter(unidad_id__in=unit_ids))
        teachers = Profesor.objects.filter(unidad_id__in=unit_ids, estado=True, usuario__estado=True,
            usuario__is_active=True, usuario__rol__activo=True, usuario__unidad_id=F('unidad_id'))
        messages = Comunicado.objects.filter(unidad_educativa_id__in=unit_ids, estado__in=['PUBLICADO', 'ARCHIVADO'])
        if calendar:
            start, end = (period.fecha_inicio, period.fecha_fin) if period else (calendar.fecha_inicio, calendar.fecha_fin)
            messages = messages.filter(publicado_at__date__range=(start, end))
        receipts = DestinatarioComunicado.objects.filter(comunicado__in=messages)
        total_receipts = receipts.count()
        metrics = {'estudiantes_activos': students.count(), 'docentes_activos': teachers.count(),
            'cursos': Curso.objects.filter(paralelo__grado__unidad_educativa_id__in=unit_ids).count(),
            'promedio': None, 'porcentaje_aprobacion': None, 'porcentaje_asistencia': None,
            'comunicados_publicados': messages.count(),
            'porcentaje_lectura': round(100 * receipts.filter(leido_at__isnull=False).count() / total_receipts, 2) if total_receipts else None}
        if calendar:
            results = valid_results(unit_ids, calendar, period)
            count = results.count()
            average = results.aggregate(value=Avg('resultado'))['value']
            metrics['promedio'] = round(float(average), 2) if average is not None else None
            metrics['porcentaje_aprobacion'] = round(100 * results.filter(condicion='APROBADO').count() / count, 2) if count else None
            sessions, legacy = attendance_queries(unit_ids, calendar, period)
            # Prefer sessions per student; legacy-only students still contribute.
            legacy = legacy.exclude(estudiante_id__in=sessions.values('historial_inscripcion__estudiante_id'))
            total = sessions.count() + legacy.count()
            present = sessions.filter(estado_asistencia='PRESENTE').count() + legacy.filter(estado='P').count()
            metrics['porcentaje_asistencia'] = round(100 * present / total, 2) if total else None
        return Response({'unidades': list(units.values('id', 'nombre')),
            'unidad_seleccionada': unit.pk if unit else None, 'gestiones': calendars,
            'gestion': selected_calendar, 'periodos': periods, 'periodo': period.pk if period else None,
            'indicadores': metrics, 'alcance': {'colegio_id': scope['colegio_id'], 'unidad_id': unit.pk if unit else None},
            'actualizado_at': timezone.now()})

# aplicaciones/personal/views.py
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import F, Q
from aplicaciones.academico.models import Curso, MateriaCurso, ResultadoAnual, ResultadoTrimestral
from aplicaciones.academico.resultados import historial_actual
from aplicaciones.usuarios.permissions import PermisoEstudianteView, PermisoPorPuesto, PermisoPorRol
from aplicaciones.usuarios.utils import get_client_ip, registrar_bitacora
from rest_framework_simplejwt.authentication import JWTAuthentication
from aplicaciones.usuarios.tenancy import es_superadmin, resolver_alcance, unidades_permitidas
from aplicaciones.usuarios.models import PermisoPuesto, PermisoRol
from aplicaciones.usuarios.auditoria import registrar_evento
from . import boletines
from .alcance_familiar import family_students
from .models import DocumentoAcademicoEmitido, Estudiante, Tutor, TutorEstudiante, HistorialInscripcion
from .serializers import (
    DocumentoAcademicoEmitidoSerializer, EstudianteSerializer, CreateEstudianteSerializer,
    GenerarBoletinSerializer, GenerarCentralizadorSerializer,
    TutorSerializer, CreateTutorSerializer,
    TutorEstudianteSerializer, CreateTutorEstudianteSerializer,
    InscripcionSerializer, HistorialInscripcionSerializer,
    NuevoEstudianteInscripcionSerializer,
)

class EstudianteViewSet(viewsets.ModelViewSet):
    queryset = Estudiante.objects.select_related('usuario','curso').all()
    permission_classes = [PermisoPorPuesto, PermisoPorRol, PermisoEstudianteView]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        user = self.request.user 
        qs = super().get_queryset()

        # SuperAdmin / Admin pueden ver todos los estudiantes
        if es_superadmin(user):
            return qs
        if hasattr(user, 'admin'):
            return qs.filter(unidad_id__in=unidades_permitidas(user))
        
        # Tutor: solo ve sus propios estudiantes
        if hasattr(user, 'tutor'):
            return qs.filter(tutores__tutor__usuario=user).distinct()
        
        # Estudiante: solo ve su propio perfil
        if hasattr(user, 'estudiante'):
            return qs.filter(usuario_id=user.pk)
        
        if hasattr(user, 'profesor'):
            prof = user.profesor
            return qs.filter(
                Q(curso__tutor_id=prof.pk) |
                Q(curso__materias__profesor=prof)
            ).distinct()
        
        return Estudiante.objects.none()  # No acceso


    def get_serializer_class(self):
        if self.action in ['crear_estudiante','editar_estudiante', 'inscribir', 'cambiar_inscripcion']:
            return InscripcionSerializer if self.action in ['inscribir', 'cambiar_inscripcion'] else CreateEstudianteSerializer
        if self.action == 'historial_inscripciones':
            return HistorialInscripcionSerializer
        return EstudianteSerializer

    @action(detail=False, methods=['get'], url_path='listar')
    def listar(self, request):
        qs = self.get_queryset()
        serializer = EstudianteSerializer(qs, many=True)
        registrar_bitacora(request.user, get_client_ip(request), 'estudiante', 'ver', 'Listar estudiantes')
        return Response(serializer.data)

    @csrf_exempt
    @action(detail=False, methods=['post'], url_path='crear')
    @transaction.atomic
    def crear_estudiante(self, request):
        data = request.data.copy()
        nuevo_estudiante = data.pop('nuevo_estudiante', None)
        if nuevo_estudiante:
            import re
            from aplicaciones.usuarios.models import Rol, Usuario

            datos_serializer = NuevoEstudianteInscripcionSerializer(
                data=nuevo_estudiante, context={'request': request}
            )
            datos_serializer.is_valid(raise_exception=True)
            datos = datos_serializer.validated_data
            if Usuario.objects.filter(ci=datos['ci']).exists():
                return Response({'ci': ['Ya existe una persona registrada con ese CI.']}, status=400)
            if Usuario.objects.filter(email__iexact=datos['email']).exists():
                return Response({'email': ['Ya existe una persona registrada con ese correo.']}, status=400)
            rol, _ = Rol.objects.get_or_create(nombre='Estudiante')
            base_username = datos.get('username', '').strip()
            base_username = base_username or re.sub(r'[^A-Za-z0-9_.-]', '', datos['ci']) or 'estudiante'
            username = base_username
            consecutivo = 1
            while Usuario.objects.filter(username=username).exists():
                consecutivo += 1
                username = f'{base_username}-{consecutivo}'
            usuario = Usuario.objects.create_user(
                ci=datos['ci'], email=datos['email'], nombre=datos['nombre'],
                apellido=datos['apellido'], password=datos.get('password') or None, username=username,
                sexo=datos['sexo'], rol=rol,
                unidad_id=data.get('unidad_id'),
            )
            data['usuario_id'] = usuario.id
        # Si el usuario debe crearse aquí, hazlo antes y asigna el id al estudiante
        usuario_data = data.pop('usuario', None)
        if usuario_data:
            from aplicaciones.usuarios.models import Usuario
            from aplicaciones.usuarios.serializer import UsuarioSerializer
            usuario_serializer = UsuarioSerializer(data=usuario_data)
            usuario_serializer.is_valid(raise_exception=True)
            usuario = usuario_serializer.save()
            data['usuario_id'] = usuario.id
        serializer = CreateEstudianteSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            est = serializer.save()
            registrar_bitacora(request.user, get_client_ip(request), 'estudiante', 'crear', f'Crear estudiante {est}')
        return Response(EstudianteSerializer(est).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put', 'patch'], url_path='editar')
    def editar_estudiante(self, request, pk=None):
        est = self.get_object()
        serializer = CreateEstudianteSerializer(
            est, data=request.data, partial=request.method == 'PATCH', context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            est = serializer.save()
            registrar_bitacora(request.user, get_client_ip(request), 'estudiante', 'editar', f'Editar estudiante {est}')
        return Response(EstudianteSerializer(est).data)

    @action(detail=True, methods=['delete'], url_path='eliminar')
    def eliminar_estudiante(self, request, pk=None):
        est = self.get_object()
        est.delete()
        registrar_bitacora(request.user, get_client_ip(request), 'estudiante', 'eliminar', f'Eliminar estudiante {pk}')
        return Response(status=status.HTTP_204_NO_CONTENT)

    # === NUEVAS ACCIONES PARA INSCRIPCIÓN ===
    
    @csrf_exempt
    @action(detail=False, methods=['post'], url_path='inscribir')
    def inscribir(self, request):
        """Inscribir nuevo estudiante en un curso"""
        serializer = InscripcionSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            with transaction.atomic():
                estudiante = serializer.create(serializer.validated_data)
                historial = HistorialInscripcion.objects.filter(
                    estudiante=estudiante,
                ).latest('pk')
                unidad = estudiante.unidad
                registrar_evento(
                    accion='CREAR', entidad='INSCRIPCION', request=request,
                    usuario=request.user, entidad_id=historial.pk,
                    colegio=unidad.colegio, unidad=unidad,
                    cambios={'campos': ('curso', 'unidad', 'estado')},
                )
                registrar_bitacora(
                    usuario=request.user,
                    ip=get_client_ip(request),
                    tabla_afectada='estudiante_inscripcion',
                    accion='inscribir',
                    descripcion=f'Inscripción nueva: {estudiante}'
                )
                return Response(
                    EstudianteSerializer(estudiante).data,
                    status=status.HTTP_201_CREATED
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @csrf_exempt
    @action(detail=True, methods=['post'], url_path='cambiar-inscripcion')
    def cambiar_inscripcion(self, request, pk=None):
        """Cambiar inscripción de un estudiante a otro curso"""
        estudiante = self.get_object()
        
        serializer = InscripcionSerializer(
            instance=estudiante,
            data=request.data,
            context={'request': request},
            partial=True
        )
        
        if serializer.is_valid():
            with transaction.atomic():
                estudiante = serializer.update(estudiante, serializer.validated_data)
                historial = HistorialInscripcion.objects.filter(
                    estudiante=estudiante,
                ).latest('pk')
                unidad = estudiante.unidad
                registrar_evento(
                    accion='ACTUALIZAR', entidad='INSCRIPCION', request=request,
                    usuario=request.user, entidad_id=historial.pk,
                    colegio=unidad.colegio, unidad=unidad,
                    cambios={'campos': ('curso', 'unidad', 'estado')},
                )
                registrar_bitacora(
                    usuario=request.user,
                    ip=get_client_ip(request),
                    tabla_afectada='estudiante_inscripcion',
                    accion='cambiar_inscripcion',
                    descripcion=f'Cambio de inscripción: {estudiante}'
                )
                return Response(EstudianteSerializer(estudiante).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='historial')
    def historial_inscripciones(self, request):
        """Obtener historial de inscripciones"""
        estudiante_id = request.query_params.get('estudiante_id')
        
        if not estudiante_id:
            return Response(
                {'detail': 'Se requiere parámetro estudiante_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            estudiantes_permitidos = self.get_queryset().values_list('usuario_id', flat=True)
            historial = HistorialInscripcion.objects.filter(
                estudiante__usuario_id=estudiante_id,
                estudiante__usuario_id__in=estudiantes_permitidos,
            ).order_by('-fecha_inscripcion')
            serializer = HistorialInscripcionSerializer(historial, many=True)
            registrar_bitacora(
                usuario=request.user,
                ip=get_client_ip(request),
                tabla_afectada='historial_inscripcion',
                accion='ver',
                descripcion=f'Ver historial de inscripciones del estudiante {estudiante_id}'
            )
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='reporte-inscripcion')
    def reporte_inscripcion(self, request):
        """Reporte de estudiantes inscritos por curso/periodo"""
        curso_id = request.query_params.get('curso_id')
        unidad_id = request.query_params.get('unidad_id')
        
        queryset = self.get_queryset().select_related('usuario', 'curso', 'unidad')
        
        if curso_id:
            queryset = queryset.filter(curso_id=curso_id)
        if unidad_id:
            queryset = queryset.filter(unidad_id=unidad_id)
        
        serializer = EstudianteSerializer(queryset, many=True)
        registrar_bitacora(
            usuario=request.user,
            ip=get_client_ip(request),
            tabla_afectada='estudiante',
            accion='reporte',
            descripcion='Generar reporte de inscripciones'
        )
        return Response({
            'total': queryset.count(),
            'datos': serializer.data
        })


class TutorViewSet(viewsets.ModelViewSet):
    queryset = Tutor.objects.select_related('usuario').all()
    permission_classes = [PermisoPorPuesto & PermisoPorRol]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        queryset = super().get_queryset()
        if es_superadmin(self.request.user):
            return queryset
        return queryset.filter(usuario__unidad_id__in=unidades_permitidas(self.request.user))

    def get_serializer_class(self):
        if self.action in ['crear_tutor','editar_tutor']:
            return CreateTutorSerializer
        return TutorSerializer

    @action(detail=False, methods=['get'], url_path='listar')
    def listar(self, request):
        serializer = TutorSerializer(self.get_queryset(), many=True)
        registrar_bitacora(request.user, get_client_ip(request), 'tutor', 'ver', 'Listar tutores')
        return Response(serializer.data)

    @csrf_exempt
    @action(detail=False, methods=['post'], url_path='crear')
    def crear_tutor(self, request):
        serializer = CreateTutorSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            t = serializer.save()
            registrar_bitacora(request.user, get_client_ip(request), 'tutor', 'crear', f'Crear tutor {t}')
        return Response(TutorSerializer(t).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put', 'patch'], url_path='editar')
    def editar_tutor(self, request, pk=None):
        t = self.get_object()
        serializer = CreateTutorSerializer(
            t, data=request.data, partial=request.method == 'PATCH', context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            t = serializer.save()
            registrar_bitacora(request.user, get_client_ip(request), 'tutor', 'editar', f'Editar tutor {t}')
        return Response(TutorSerializer(t).data)

    @action(detail=True, methods=['delete'], url_path='eliminar')
    def eliminar_tutor(self, request, pk=None):
        t = self.get_object()
        t.delete()
        registrar_bitacora(request.user, get_client_ip(request), 'tutor', 'eliminar', f'Eliminar tutor {pk}')
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=["get"], url_path="usuario/(?P<usuario_id>[^/.]+)")
    def get_by_usuario(self, request, usuario_id=None):
        try:
            tutor = self.get_queryset().get(usuario_id=usuario_id)
            serializer = self.get_serializer(tutor)
            return Response(serializer.data)
        except Tutor.DoesNotExist:
            return Response({"detail": "No existe"}, status=status.HTTP_404_NOT_FOUND)


class TutorEstudianteViewSet(viewsets.ModelViewSet):
    queryset = TutorEstudiante.objects.select_related('tutor__usuario','estudiante__usuario').all()
    permission_classes = [PermisoPorPuesto & PermisoPorRol]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        queryset = super().get_queryset()
        if es_superadmin(self.request.user):
            return queryset
        return queryset.filter(estudiante__unidad_id__in=unidades_permitidas(self.request.user))

    def get_serializer_class(self):
        if self.action in ['crear_relacion','editar_relacion']:
            return CreateTutorEstudianteSerializer
        return TutorEstudianteSerializer

    @action(detail=False, methods=['get'], url_path='listar')
    def listar(self, request):
        data = TutorEstudianteSerializer(self.get_queryset(), many=True)
        registrar_bitacora(request.user, get_client_ip(request), 'tutor_estudiante', 'ver', 'Listar relaciones')
        return Response(data.data)

    @csrf_exempt
    @action(detail=False, methods=['post'], url_path='crear')
    def crear_relacion(self, request):
        serializer = CreateTutorEstudianteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            rel = serializer.save()
            registrar_bitacora(request.user, get_client_ip(request), 'tutor_estudiante', 'crear', f'Crear relación {rel}')
        return Response(TutorEstudianteSerializer(rel).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put'], url_path='editar')
    def editar_relacion(self, request, pk=None):
        rel = self.get_object()
        serializer = CreateTutorEstudianteSerializer(
            rel, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            rel = serializer.save()
            registrar_bitacora(request.user, get_client_ip(request), 'tutor_estudiante', 'editar', f'Editar relación {rel}')
        return Response(TutorEstudianteSerializer(rel).data)

    @action(detail=True, methods=['delete'], url_path='eliminar')
    def eliminar_relacion(self, request, pk=None):
        rel = self.get_object()
        rel.delete()
        registrar_bitacora(request.user, get_client_ip(request), 'tutor_estudiante', 'eliminar', f'Eliminar relación {pk}')
        return Response(status=status.HTTP_204_NO_CONTENT)


class PermisoDocumentoAcademico(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        accion = {'list': 'listar', 'retrieve': 'listar', 'estudiantes_curso': 'listar',
                  'generar_boletin': 'generar', 'generar_centralizador': 'generar',
                  'descargar': 'descargar'}.get(view.action)
        if accion is None:
            return False
        if hasattr(user, 'admin'):
            return PermisoPuesto.objects.filter(puesto_id=user.admin.puesto_id, modelo__nombre='documento-academico', accion__nombre=accion).exists()
        return PermisoRol.objects.filter(rol_id=user.rol_id, modelo__nombre='documento-academico', accion__nombre=accion).exists()


class DocumentoAcademicoEmitidoViewSet(viewsets.ReadOnlyModelViewSet):
    """HU-19: boletines individuales y centralizadores emitidos."""

    serializer_class = DocumentoAcademicoEmitidoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoDocumentoAcademico]

    def get_queryset(self):
        queryset = DocumentoAcademicoEmitido.objects.select_related(
            'historial_inscripcion__estudiante__usuario', 'curso', 'periodo',
            'calendario_academico',
        ).order_by('-emitido_at')
        user = self.request.user
        family = hasattr(user, 'estudiante') or hasattr(user, 'tutor')
        if family:
            queryset = queryset.filter(tipo=DocumentoAcademicoEmitido.Tipo.BOLETIN,
                historial_inscripcion__estudiante__in=family_students(user),
                historial_inscripcion__unidad_id=F('calendario_academico__unidad_educativa_id'),
                historial_inscripcion__curso_nuevo__paralelo__grado__unidad_educativa_id=F('historial_inscripcion__unidad_id'),
                historial_inscripcion__estudiante__unidad_id=F('historial_inscripcion__unidad_id'),
            ).filter(Q(periodo__isnull=True) | Q(periodo__calendario_id=F('calendario_academico_id')))
        elif resolver_alcance(user)['tipo'] == 'GLOBAL':
            colegio = self.request.headers.get('X-Colegio-ID', '')
            if not colegio.isascii() or not colegio.isdecimal() or int(colegio) <= 0:
                raise PermissionDenied('Seleccione un colegio mediante X-Colegio-ID.')
            queryset = queryset.filter(calendario_academico__unidad_educativa__colegio_id=int(colegio))
        else:
            permitidas = unidades_permitidas(user)
            queryset = queryset.filter(
                calendario_academico__unidad_educativa_id__in=permitidas,
            )

        # Autoservicio: tutor/estudiante solo ven sus propios boletines, nunca
        # centralizadores ni los de otros estudiantes de la misma unidad.
        if hasattr(user, 'estudiante'):
            queryset = queryset.filter(
                tipo=DocumentoAcademicoEmitido.Tipo.BOLETIN,
                historial_inscripcion__estudiante__usuario=user,
            )
        elif hasattr(user, 'tutor'):
            queryset = queryset.filter(
                tipo=DocumentoAcademicoEmitido.Tipo.BOLETIN,
                historial_inscripcion__estudiante__tutores__tutor__usuario=user,
            ).distinct()

        params = self.request.query_params
        filtros = {
            'historial_inscripcion': 'historial_inscripcion_id',
            'periodo': 'periodo_id', 'calendario_academico': 'calendario_academico_id',
            'tipo': 'tipo',
        }
        for parametro, campo in filtros.items():
            valor = params.get(parametro)
            if valor:
                queryset = queryset.filter(**{campo: valor})
        if params.get('curso'):
            queryset = queryset.filter(
                Q(curso_id=params['curso']) | Q(historial_inscripcion__curso_nuevo_id=params['curso'])
            )
        return queryset

    def _validar_ambito(self, unidad):
        if resolver_alcance(self.request.user)['tipo'] == 'GLOBAL':
            colegio = self.request.headers.get('X-Colegio-ID', '')
            if not colegio.isascii() or not colegio.isdecimal() or int(colegio) <= 0 or unidad.colegio_id != int(colegio):
                raise PermissionDenied('Seleccione un colegio válido mediante X-Colegio-ID.')
            return
        permitidas = unidades_permitidas(self.request.user)
        if permitidas is not None and unidad.pk not in permitidas:
            raise PermissionDenied('No pertenece a su ámbito institucional.')

    @action(detail=False, methods=['post'], url_path='generar-boletin')
    def generar_boletin(self, request):
        serializer = GenerarBoletinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        historial = serializer.validated_data['historial_inscripcion']
        self._validar_ambito(historial.unidad)
        try:
            with transaction.atomic():
                documento, _ = boletines.emitir_boletin(
                    historial, serializer.validated_data['calendario_academico'],
                    periodo=serializer.validated_data.get('periodo'), usuario=request.user,
                )
                registrar_evento(
                    accion='CREAR', entidad='DOCUMENTO_ACADEMICO', request=request,
                    entidad_id=documento.pk, unidad=historial.unidad,
                    cambios={'campos': ('tipo', 'version')},
                )
        except ValueError as error:
            # La configuración de evaluación es un requisito del dominio, no un error interno.
            raise serializers.ValidationError({'calendario_academico': str(error)}) from error
        return Response(DocumentoAcademicoEmitidoSerializer(documento).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='generar-centralizador')
    def generar_centralizador(self, request):
        serializer = GenerarCentralizadorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        curso = serializer.validated_data['curso']
        unidad = curso.paralelo.grado.unidad_educativa
        self._validar_ambito(unidad)
        with transaction.atomic():
            documento, _ = boletines.emitir_centralizador(
                curso, serializer.validated_data['calendario_academico'],
                periodo=serializer.validated_data.get('periodo'), usuario=request.user,
            )
            registrar_evento(
                accion='CREAR', entidad='DOCUMENTO_ACADEMICO', request=request,
                entidad_id=documento.pk, unidad=unidad,
                cambios={'campos': ('tipo', 'version')},
            )
        return Response(DocumentoAcademicoEmitidoSerializer(documento).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='descargar')
    def descargar(self, request, pk=None):
        documento = self.get_object()
        archivo = default_storage.open(documento.archivo_ref, 'rb')
        respuesta = FileResponse(archivo, content_type=documento.archivo_mime)
        nombre = f'{documento.tipo.lower()}_{documento.pk}_v{documento.version}.pdf'
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
        return respuesta

    @action(detail=False, methods=['get'], url_path='estudiantes-curso')
    def estudiantes_curso(self, request):
        """Estudiantes de un curso con su historial_inscripcion vigente,
        para elegir a quién generarle un boletín individual (HU-19)."""
        curso_id = request.query_params.get('curso')
        if not curso_id:
            raise serializers.ValidationError({'curso': 'Parámetro requerido.'})
        curso = get_object_or_404(Curso, pk=curso_id)
        self._validar_ambito(curso.paralelo.grado.unidad_educativa)

        historiales = HistorialInscripcion.objects.filter(
            curso_nuevo=curso, estudiante__curso=curso,
        ).select_related('estudiante__usuario').order_by('estudiante_id', '-fecha_inscripcion')

        vistos = set()
        filas = []
        for historial in historiales:
            if historial.estudiante_id in vistos:
                continue
            vistos.add(historial.estudiante_id)
            filas.append({
                'estudiante': historial.estudiante_id,
                'estudiante_nombre': str(historial.estudiante.usuario),
                'historial_inscripcion': historial.pk,
            })
        filas.sort(key=lambda fila: fila['estudiante_nombre'])
        return Response(filas)


class PermisoResultadosPropios(BasePermission):
    """Solo tutor (de sus hijos) o estudiante (de sí mismo). Deliberadamente
    no reutiliza PermisoPorRol/PermisoPorPuesto: es un autoservicio de solo
    lectura, no una acción administrativa que necesite permisos sembrados."""

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        return hasattr(user, 'estudiante') or hasattr(user, 'tutor')


class MisResultadosView(APIView):
    """Resultados ya calculados (HU-17) del propio estudiante, o de un hijo
    a cargo del tutor autenticado. Las vistas administrativas de evaluación
    (CalificacionViewSet, ActividadEvaluacionViewSet, correcciones_api)
    devuelven queryset.none() para tutor/estudiante a propósito; este
    endpoint es la vía de autoservicio, acotada por pertenencia, no por
    permisos de puesto/rol."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoResultadosPropios]

    def get(self, request):
        user = request.user
        estudiante_id = request.query_params.get('estudiante')

        if hasattr(user, 'estudiante'):
            estudiante = user.estudiante
            if estudiante_id and str(estudiante.pk) != estudiante_id:
                raise PermissionDenied('No puede consultar los resultados de otro estudiante.')
        else:
            hijos = Estudiante.objects.filter(tutores__tutor__usuario=user).select_related('usuario')
            if estudiante_id:
                estudiante = hijos.filter(pk=estudiante_id).first()
                if estudiante is None:
                    raise PermissionDenied('El estudiante no está a su cargo.')
            elif hijos.count() == 1:
                estudiante = hijos.first()
            else:
                return Response({
                    'detail': 'Indique a qué estudiante consultar con el parámetro "estudiante".',
                    'hijos': [
                        {'estudiante': hijo.pk, 'estudiante_nombre': str(hijo.usuario)}
                        for hijo in hijos
                    ],
                }, status=status.HTTP_400_BAD_REQUEST)

        historial = historial_actual(estudiante)
        if historial is None:
            return Response({'estudiante': estudiante.pk, 'estudiante_nombre': str(estudiante.usuario), 'materias': []})

        materias = [
            materia_curso.materia for materia_curso in MateriaCurso.objects.filter(
                curso=historial.curso_nuevo,
            ).select_related('materia').order_by('materia__nombre')
        ]
        trimestrales_por_materia = {}
        for resultado in ResultadoTrimestral.objects.filter(
            historial_inscripcion=historial, materia__in=materias,
        ).select_related('periodo'):
            trimestrales_por_materia.setdefault(resultado.materia_id, []).append({
                'periodo': resultado.periodo_id,
                'periodo_nombre': resultado.periodo.nombre,
                'resultado': str(resultado.resultado),
                'condicion': resultado.condicion,
            })
        anuales_por_materia = {
            resultado.materia_id: resultado
            for resultado in ResultadoAnual.objects.filter(
                historial_inscripcion=historial, materia__in=materias,
            )
        }

        materias_datos = []
        for materia in materias:
            anual = anuales_por_materia.get(materia.pk)
            materias_datos.append({
                'materia': materia.pk,
                'materia_nombre': materia.nombre,
                'trimestrales': trimestrales_por_materia.get(materia.pk, []),
                'anual': (
                    {'resultado': str(anual.resultado), 'condicion': anual.condicion}
                    if anual else None
                ),
            })

        return Response({
            'estudiante': estudiante.pk,
            'estudiante_nombre': str(estudiante.usuario),
            'curso': historial.curso_nuevo.nombre,
            'materias': materias_datos,
        })

from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Admin, PermisoPuesto, PermisoRol, Puesto, Rol, Usuario
from .serializer import (
    AdminSerializer,
    PermisoPuestoSerializer,
    PermisoRolSerializer,
    UsuarioSerializer,
    RolSerializer,
    PuestoSerializer,
)
from .utils import get_client_ip, registrar_bitacora
from .permissions import IsSuperAdmin
from .auditoria import registrar_evento
from .tenancy import resolver_alcance, validar_unidad


def _es_superadmin_usuario(usuario):
    from .tenancy import es_superadmin
    return es_superadmin(usuario)


def _puede(request, modelo):
    if _es_superadmin_usuario(request.user):
        return True
    from .privilegios import puede
    accion = {
        'GET': 'listar', 'POST': 'crear', 'PUT': 'editar',
        'PATCH': 'editar', 'DELETE': 'eliminar',
    }.get(request.method)
    return bool(accion and puede(request.user, modelo, accion))


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = str(request.data.get('email', '')).strip()
    username_compat = str(request.data.get('username', '')).strip()
    password = request.data.get('password', '')

    if not (email or username_compat) or not password:
        registrar_evento(
            accion='LOGIN_FALLIDO', entidad='AUTENTICACION', request=request,
            identificador=email or username_compat,
            cambios={'resultado': 'CREDENCIALES_INCOMPLETAS'},
        )
        return Response(
            {'error': 'Correo electrónico y contraseña son obligatorios.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if email:
        usuario_registrado = Usuario.objects.filter(email__iexact=email).first()
    else:
        # Compatibilidad transitoria mientras React migra de username a email.
        usuario_registrado = Usuario.objects.filter(username=username_compat).first()

    if usuario_registrado is None:
        registrar_evento(
            accion='LOGIN_FALLIDO', entidad='AUTENTICACION', request=request,
            identificador=email or username_compat,
            cambios={'resultado': 'CREDENCIALES_INVALIDAS'},
        )
        return Response(
            {'error': 'Credenciales inválidas.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not usuario_registrado.is_active:
        # Las cuentas nuevas del registro institucional quedan habilitadas
        # para usar de inmediato sus credenciales. Esto también recupera
        # registros anteriores pendientes, solo si la contraseña es válida.
        es_registro_institucional = (
            usuario_registrado.check_password(password)
            and hasattr(usuario_registrado, 'registro_institucional')
        )
        if es_registro_institucional:
            usuario_registrado.is_active = True
            usuario_registrado.save(update_fields=['is_active'])
            registrar_evento(
                accion='ACTUALIZAR', entidad='AUTENTICACION', request=request,
                usuario=usuario_registrado, cambios={'resultado': 'CREDENCIALES_VALIDAS'},
            )
        else:
            registrar_evento(
                accion='LOGIN_FALLIDO', entidad='AUTENTICACION', request=request,
                identificador=email or username_compat,
                cambios={'resultado': 'CREDENCIALES_INVALIDAS'},
            )
            return Response(
                {'error': 'Credenciales inválidas.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

    usuario = authenticate(
        request=request,
        username=usuario_registrado.username,
        password=password,
    )
    if usuario is None:
        registrar_evento(
            accion='LOGIN_FALLIDO', entidad='AUTENTICACION', request=request,
            identificador=email or username_compat,
            cambios={'resultado': 'CREDENCIALES_INVALIDAS'},
        )
        return Response(
            {'error': 'Credenciales inválidas.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    refresh = RefreshToken.for_user(usuario)
    access = refresh.access_token
    update_last_login(None, usuario)
    registrar_evento(
        accion='LOGIN_EXITOSO', entidad='AUTENTICACION', request=request,
        usuario=usuario, cambios={'resultado': 'EXITOSO'},
    )
    registrar_bitacora(
        usuario,
        get_client_ip(request),
        'usuario',
        'crear',
        'Inicio de sesión exitoso',
    )
    return Response({
        'access': str(access),
        'refresh': str(refresh),
        'expires_in': int(access.lifetime.total_seconds()),
        'access_expires_at': access['exp'],
        'refresh_expires_at': refresh['exp'],
        # Alias temporal para el frontend actual.
        'token': str(access),
        'user': UsuarioSerializer(usuario, context={'request': request}).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def perfil(request):
    return Response(UsuarioSerializer(request.user, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        registrar_evento(
            accion='LOGOUT', entidad='AUTENTICACION', request=request,
            cambios={'resultado': 'REFRESH_AUSENTE'},
        )
        return Response(
            {'error': 'El refresh token es obligatorio.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        RefreshToken(refresh_token).blacklist()
        registrar_evento(
            accion='LOGOUT', entidad='AUTENTICACION', request=request,
            cambios={'resultado': 'EXITOSO'},
        )
    except TokenError:
        registrar_evento(
            accion='LOGOUT', entidad='AUTENTICACION', request=request,
            cambios={'resultado': 'REFRESH_INVALIDO'},
        )
        return Response(
            {'error': 'Refresh token inválido o vencido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response({'message': 'Sesión cerrada correctamente.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_detail(request, usuario_id):
    if request.user.pk != usuario_id and not _es_superadmin_usuario(request.user):
        return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        admin = Admin.objects.select_related('usuario', 'puesto', 'unidad', 'colegio').get(
            usuario_id=usuario_id
        )
    except Admin.DoesNotExist:
        return Response(
            {'detail': 'Administrador no encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(AdminSerializer(admin, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def permisos_puesto(request):
    puesto_id = request.query_params.get('puesto_id')
    if not _es_superadmin_usuario(request.user):
        if not hasattr(request.user, 'admin') or str(request.user.admin.puesto_id) != str(puesto_id):
            return Response({'detail': 'No autorizado.'}, status=403)
    queryset = PermisoPuesto.objects.select_related('puesto', 'modelo', 'accion')
    if puesto_id:
        queryset = queryset.filter(puesto_id=puesto_id)
    else:
        queryset = queryset.none()
    return Response(PermisoPuestoSerializer(queryset, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def permisos_rol(request):
    rol_id = request.query_params.get('rol_id')
    if not _es_superadmin_usuario(request.user) and str(request.user.rol_id) != str(rol_id):
        return Response({'detail': 'No autorizado.'}, status=403)
    queryset = PermisoRol.objects.select_related('rol', 'modelo', 'accion')
    if rol_id:
        queryset = queryset.filter(rol_id=rol_id)
    else:
        queryset = queryset.none()
    return Response(PermisoRolSerializer(queryset, many=True).data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def usuarios(request):
    # Política de suscripciones SaaS (HU-SE01): un colegio con suscripción
    # restringida no puede gestionar usuarios; los módulos se validan aquí.
    from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
    autorizar_acceso_modelo(request.user, 'usuario')

    if not _puede(request, 'usuario'):
        return Response({'detail': 'No tiene permiso para gestionar usuarios.'}, status=403)
    if request.method == 'POST':
        serializer = UsuarioSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        # Límite de usuarios del plan vigente (HU-SE01 regla 6).
        from aplicaciones.suscripciones.servicios import (
            colegio_para_alta, validar_limite_usuarios,
        )
        colegio_id = colegio_para_alta(serializer.validated_data)
        if colegio_id:
            validar_limite_usuarios(colegio_id)
        usuario = serializer.save()
        registrar_evento(
            accion='CREAR', entidad='USUARIO', request=request,
            entidad_id=usuario.pk,
            cambios={'campos': serializer.validated_data.keys()},
        )
        return Response(
            UsuarioSerializer(usuario, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )
    queryset = Usuario.objects.select_related('rol', 'unidad', 'unidad__colegio').all()
    alcance = resolver_alcance(request.user)
    if alcance['tipo'] == 'COLEGIO':
        queryset = queryset.filter(
            Q(unidad__colegio_id=alcance['colegio_id'])
            | Q(admin__colegio_id=alcance['colegio_id'])
        ).distinct()
    elif alcance['tipo'] != 'GLOBAL':
        queryset = queryset.filter(unidad_id=alcance['unidad_id'])
    queryset = queryset.order_by('apellido', 'nombre')
    return Response(UsuarioSerializer(queryset, many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def roles(request):
    nombres_base = ['Admin', 'Profesor', 'Tutor', 'Estudiante']
    queryset = Rol.objects.filter(nombre__in=nombres_base)
    if hasattr(request.user, 'admin'):
        puesto = getattr(request.user.admin.puesto, 'nombre', '').strip().lower()
        if puesto != 'director':
            queryset = queryset.exclude(nombre='Admin')
    return Response(RolSerializer(queryset.order_by('nombre'), many=True).data)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def usuario_detail(request, pk):
    # Política de suscripciones SaaS (HU-SE01)
    from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
    autorizar_acceso_modelo(request.user, 'usuario')

    if not _puede(request, 'usuario'):
        return Response({'detail': 'No tiene permiso para gestionar usuarios.'}, status=403)
    try:
        usuario = Usuario.objects.select_related('rol').get(pk=pk)
    except Usuario.DoesNotExist:
        return Response({'detail': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _es_superadmin_usuario(request.user):
        try:
            validar_unidad(request.user, usuario.unidad)
        except Exception as exc:
            return Response({'detail': str(exc.detail)}, status=403)

    if request.method == 'GET':
        return Response(UsuarioSerializer(usuario, context={'request': request}).data)
    if request.method == 'DELETE':
        if usuario.pk == request.user.pk:
            return Response(
                {'detail': 'No puede eliminar su propia cuenta mientras está en sesión.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        usuario_id = usuario.pk
        usuario.delete()
        registrar_evento(
            accion='ELIMINAR', entidad='USUARIO', request=request,
            entidad_id=usuario_id,
            cambios={'resultado': 'ELIMINADO'},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = UsuarioSerializer(
        usuario,
        data=request.data,
        partial=request.method == 'PATCH',
        context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    registrar_evento(
        accion='ACTUALIZAR', entidad='USUARIO', request=request,
        entidad_id=usuario.pk,
        cambios={'campos': serializer.validated_data.keys()},
    )
    return Response(UsuarioSerializer(usuario, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def rol_detail(request, pk):
    try:
        rol = Rol.objects.get(pk=pk)
    except Rol.DoesNotExist:
        return Response({'detail': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(RolSerializer(rol).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def puestos(request):
    if not (_es_superadmin_usuario(request.user) or hasattr(request.user, 'admin')):
        return Response({'detail': 'No autorizado.'}, status=403)
    queryset = Puesto.objects.all()
    if hasattr(request.user, 'admin'):
        queryset = queryset.exclude(nombre__iexact='Director')
    return Response(PuestoSerializer(queryset.order_by('nombre'), many=True).data)

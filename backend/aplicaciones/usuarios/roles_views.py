"""HU-SE02: API de gestión de usuarios, roles y privilegios granulares.

Endpoints:
- GET/POST  /api/usuarios/roles/                 lista y creación de roles
- GET/PUT/PATCH/DELETE /api/usuarios/roles/<pk>/ detalle y ciclo de vida
- GET/PUT   /api/usuarios/roles/<pk>/permisos/   permisos funcionales
- GET/PUT   /api/usuarios/roles/<pk>/componentes/ permisos de interfaz
- PUT       /api/usuarios/usuarios/<pk>/roles/   asignación de roles extra
- GET       /api/usuarios/acciones/              catálogo de acciones
- GET       /api/usuarios/modelos-permitidos/    catálogo de modelos

Reglas de negocio:
- El Superadmin opera a nivel global; un administrador del colegio solo
  crea/edita roles de su propio colegio (tenant).
- Denegación por defecto: un rol nuevo no concede nada hasta que se asignen
  permisos explícitos.
- Un administrador no puede delegar privilegios superiores a los suyos.
- Toda creación, modificación o revocación queda registrada en auditoría.
"""

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo

from .api_views import _es_superadmin_usuario, _puede
from .auditoria import registrar_evento
from .models import (
    Accion, Admin, ModeloPermitido, PermisoComponente, PermisoRol, Puesto, Rol, Usuario,
)
from .privilegios import (
    es_superadmin, permisos_funcionales, roles_no_delegables, rol_asignable,
    validar_no_escalacion,
)
from .serializer import (
    AccionSerializer, AsignarRolesSerializer, ModeloPermitidoSerializer,
    PermisoComponenteSerializer, RolComponentesPayloadSerializer,
    RolPermisosPayloadSerializer, RolSerializer,
)
from .tenancy import validar_unidad


def _colegio_solicitante(user):
    """Colegio (tenant) del administrador solicitante, o None si no aplica."""
    if es_superadmin(user):
        return None
    admin = getattr(user, 'admin', None)
    if admin is not None and admin.colegio_id:
        return admin.colegio_id
    unidad = getattr(user, 'unidad', None)
    if unidad is not None and unidad.colegio_id:
        return unidad.colegio_id
    if admin is not None and admin.unidad_id:
        return admin.unidad.colegio_id
    return None


def _gestion_puede(request, modelo='rol'):
    """¿El solicitante puede gestionar el modelo dado? (SuperAdmin o permiso de puesto)."""
    if _es_superadmin_usuario(request.user):
        return True
    return _puede(request, modelo)


def _es_director(request):
    if _es_superadmin_usuario(request.user):
        return True
    admin = getattr(request.user, 'admin', None)
    return bool(admin is not None and getattr(admin.puesto, 'nombre', '').strip().lower() == 'director')


def _puede_gestionar_rol(request, rol):
    """Alcance: SuperAdmin → cualquier rol; admin → solo roles de su colegio."""
    if _es_superadmin_usuario(request.user):
        return True
    if not _es_director(request):
        return False
    colegio_id = _colegio_solicitante(request.user)
    if colegio_id is None or rol.colegio_id is None:
        # Un admin no gestiona roles de sistema ni de otros tenants.
        return False
    return rol.colegio_id == colegio_id


def _rol_institucional_desde_admin(request, rol):
    """Convierte la vista del rol base Admin en una configuración del tenant.

    El catálogo conserva el rol base global para compatibilidad, pero las
    concesiones del Director nunca se escriben sobre ese registro global.
    """
    if not _es_director(request) or rol.categoria != Rol.Categoria.BASE or rol.nombre.casefold() != 'admin':
        return rol
    admin = request.user.admin
    from aplicaciones.institucion.models import Colegio
    puesto = Puesto.objects.filter(nombre__iexact='Secretaria').first()
    if puesto is None:
        puesto = Puesto.objects.filter(nombre__iexact='Secretaría').first()
    with transaction.atomic():
        Colegio.objects.select_for_update().get(pk=admin.colegio_id)
        nombre = 'Admin'
        if admin.unidad_id:
            nombre = f'Admin · {admin.unidad.nombre}'[:50]
        institucional = Rol.objects.filter(
            categoria=Rol.Categoria.FUNCIONAL,
            colegio_id=admin.colegio_id,
            unidad_educativa_id=admin.unidad_id,
            puesto_id=puesto.pk if puesto else None,
        ).first()
        if institucional is None:
            institucional = Rol.objects.create(
                nombre=nombre,
                descripcion='Permisos institucionales del personal administrativo.',
                colegio_id=admin.colegio_id,
                unidad_educativa=admin.unidad,
                puesto=puesto,
                categoria=Rol.Categoria.FUNCIONAL,
                activo=True,
            )
    return institucional


def _respuesta_no_autorizado():
    return Response({'detail': 'No tiene permiso para gestionar roles.'}, status=403)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def roles(request):
    autorizar_acceso_modelo(request.user, 'rol')

    if request.method == 'POST':
        return _crear_rol(request)

    query = request.query_params
    if query.get('asignables') == '1':
        return _roles_asignables(request)
    if query.get('gestion') == '1':
        return _roles_gestion(request)

    # Comportamiento histórico: roles base del sistema para el formulario de
    # usuarios ( Director ve también 'Admin' ).
    queryset = Rol.objects.filter(
        categoria=Rol.Categoria.BASE, activo=True, colegio__isnull=True,
    )
    if hasattr(request.user, 'admin'):
        puesto = getattr(request.user.admin.puesto, 'nombre', '').strip().lower()
        if puesto != 'director':
            queryset = queryset.exclude(nombre='Admin')
        else:
            queryset = queryset.exclude(nombre__iexact='SuperAdmin')
    return Response(RolSerializer(queryset.order_by('nombre'), many=True).data)


def _crear_rol(request):
    if not _gestion_puede(request) or not _es_director(request):
        return _respuesta_no_autorizado()

    datos = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    if not _es_superadmin_usuario(request.user):
        colegio_id = _colegio_solicitante(request.user)
        if colegio_id is None:
            return Response(
                {'detail': 'El administrador no tiene colegio asignado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            'colegio_id' in datos and datos['colegio_id'] is not None
            and int(datos['colegio_id']) != colegio_id
        ):
            return Response(
                {'detail': 'Solo puede crear roles para su propio colegio.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Se inyecta ANTES de validar para que la unicidad de nombre se
        # compruebe en el alcance real (colegio del solicitante).
        datos['colegio_id'] = colegio_id
        unidad_id = datos.get('unidad_id')
        if unidad_id is not None:
            from aplicaciones.institucion.models import UnidadEducativa
            unidad = UnidadEducativa.objects.filter(pk=unidad_id).first()
            if unidad is None or unidad.colegio_id != colegio_id:
                return Response({'detail': 'La unidad no pertenece a su colegio.'}, status=403)

    serializer = RolSerializer(data=datos, context={'request': request})
    serializer.is_valid(raise_exception=True)
    rol = serializer.save()
    registrar_evento(
        accion='CREAR', entidad='ROL', request=request, entidad_id=rol.pk,
        colegio=rol.colegio,
        cambios={'campos': ('nombre', 'colegio', 'descripcion')},
    )
    return Response(RolSerializer(rol).data, status=status.HTTP_201_CREATED)


def _roles_gestion(request):
    """Lista para la página de administración de roles (HU-SE02)."""
    if not _gestion_puede(request):
        return _respuesta_no_autorizado()
    queryset = Rol.objects.select_related('colegio').order_by('colegio', 'nombre')
    if not _es_superadmin_usuario(request.user):
        colegio_id = _colegio_solicitante(request.user)
        from django.db.models import Q
        queryset = queryset.filter(
            Q(colegio_id__isnull=True)
            | Q(colegio_id=colegio_id)
        ).exclude(nombre__iexact='SuperAdmin')
    return Response(RolSerializer(queryset, many=True).data)


def _roles_asignables(request):
    """Roles personalizados activos asignables como roles adicionales."""
    if not (_es_superadmin_usuario(request.user) or hasattr(request.user, 'admin')):
        return _respuesta_no_autorizado()
    from django.db.models import Q
    queryset = Rol.objects.filter(
        activo=True, categoria=Rol.Categoria.FUNCIONAL,
        permisos__isnull=False,
    ).distinct().order_by('nombre')
    if not _es_superadmin_usuario(request.user):
        colegio_id = _colegio_solicitante(request.user)
        if colegio_id is None:
            queryset = Rol.objects.none()
        else:
            unidad_id = getattr(request.user, 'unidad_id', None)
            queryset = queryset.filter(
                Q(colegio_id__isnull=True, unidad_educativa__isnull=True)
                | Q(colegio_id=colegio_id, unidad_educativa__isnull=True)
                | Q(colegio_id=colegio_id, unidad_educativa_id=unidad_id)
            )
    return Response(RolSerializer(queryset, many=True).data)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def rol_detail(request, pk):
    autorizar_acceso_modelo(request.user, 'rol')
    try:
        rol = Rol.objects.select_related('colegio').get(pk=pk)
    except Rol.DoesNotExist:
        return Response({'detail': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        # Cualquier usuario autenticado puede consultar roles de su ámbito
        # (el formulario de usuarios los necesita); los de otros colegios no.
        if not _es_superadmin_usuario(request.user):
            colegio_id = _colegio_solicitante(request.user)
            if rol.colegio_id is None and rol.nombre.strip().lower() == 'superadmin':
                return Response({'detail': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
            if rol.colegio_id is not None and rol.colegio_id != colegio_id:
                return Response({'detail': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RolSerializer(rol).data)

    if not _puede_gestionar_rol(request, rol):
        return _respuesta_no_autorizado()
    if not _gestion_puede(request):
        return _respuesta_no_autorizado()

    if request.method == 'DELETE':
        if rol.categoria == Rol.Categoria.BASE or rol.colegio_id is None:
            return Response(
                {'detail': 'Los roles del sistema no pueden eliminarse.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rol_id = rol.pk
        colegio = rol.colegio
        rol.activo = False
        rol.save(update_fields=['activo'])
        registrar_evento(
            accion='ELIMINAR', entidad='ROL', request=request, entidad_id=rol_id,
            colegio=colegio, cambios={'resultado': 'ELIMINADO', 'campos': ('nombre',)},
        )
        return Response(RolSerializer(rol).data)

    serializer = RolSerializer(
        rol, data=request.data, partial=request.method == 'PATCH',
        context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    if rol.categoria == Rol.Categoria.BASE:
        return Response({'detail': 'Los roles base no pueden modificarse.'}, status=400)
    if 'colegio' in serializer.validated_data and not _es_superadmin_usuario(request.user):
        return Response(
            {'detail': 'No puede cambiar el colegio de un rol.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer.save()
    registrar_evento(
        accion='ACTUALIZAR', entidad='ROL', request=request, entidad_id=rol.pk,
        colegio=rol.colegio,
        cambios={'campos': serializer.validated_data.keys()},
    )
    return Response(RolSerializer(rol).data)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def rol_permisos(request, pk):
    """HU-SE02 regla 3: permisos funcionales (modelo + acción) de un rol."""
    autorizar_acceso_modelo(request.user, 'rol')
    try:
        rol = Rol.objects.get(pk=pk)
    except Rol.DoesNotExist:
        return Response({'detail': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        if not _es_superadmin_usuario(request.user):
            colegio_id = _colegio_solicitante(request.user)
            if rol.colegio_id is not None and rol.colegio_id != colegio_id:
                return Response({'detail': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        permisos = [
            {'modelo': permiso.modelo.nombre, 'accion': permiso.accion.nombre}
            for permiso in rol.permisos.select_related('modelo', 'accion').order_by(
                'modelo__nombre', 'accion__nombre',
            )
        ]
        propios = set(permisos_funcionales(request.user) or set())
        metadatos = [
            {
                **permiso,
                'directo': True,
                'heredado': False,
                'disponible': (permiso['modelo'], permiso['accion']) in propios
                    or _es_superadmin_usuario(request.user),
                'bloqueado': not _es_superadmin_usuario(request.user)
                    and (permiso['modelo'], permiso['accion']) not in propios,
                'motivo_bloqueo': None if (
                    _es_superadmin_usuario(request.user)
                    or (permiso['modelo'], permiso['accion']) in propios
                ) else 'Supera el techo de privilegios del solicitante.',
            }
            for permiso in permisos
        ]
        return Response({'rol_id': rol.pk, 'permisos': permisos, 'metadatos': metadatos})

    rol = _rol_institucional_desde_admin(request, rol)

    if not _puede_gestionar_rol(request, rol) or not _gestion_puede(request):
        return _respuesta_no_autorizado()

    serializer = RolPermisosPayloadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pares = serializer.validated_data['permisos']

    # Regla final: no delegar privilegios superiores a los propios.
    denegados = validar_no_escalacion(request.user, pares)
    if denegados:
        detalle = ', '.join(f'{m}.{a}' for m, a in denegados)
        return Response(
            {'detail': (
                'No puede conceder permisos que usted no posee: ' + detalle + '.'
            )},
            status=status.HTTP_403_FORBIDDEN,
        )

    acciones_dependientes = {
        'crear', 'editar', 'desactivar', 'eliminar',
        'descargar', 'generar', 'aprobar',
    }
    base_por_modelo = {
        modelo for modelo, accion in pares if accion in {'listar', 'ver'}
    }
    incoherentes = sorted({
        modelo for modelo, accion in pares
        if accion in acciones_dependientes and modelo not in base_por_modelo
    })
    if incoherentes:
        return Response(
            {'detail': 'Cada permiso dependiente requiere listar o ver: '
                       + ', '.join(incoherentes) + '.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        rol.permisos.all().delete()
        filas = []
        for modelo_nombre, accion_nombre in pares:
            modelo = ModeloPermitido.objects.get(nombre=modelo_nombre)
            accion = Accion.objects.get(nombre=accion_nombre)
            filas.append(PermisoRol(rol=rol, modelo=modelo, accion=accion))
        PermisoRol.objects.bulk_create(filas)

    registrar_evento(
        accion='ACTUALIZAR', entidad='PERMISO_ROL', request=request,
        entidad_id=rol.pk, colegio=rol.colegio,
        cambios={'campos': ['permisos'], 'resultado': f'{len(pares)} permisos'},
    )
    return Response({'rol_id': rol.pk, 'permisos': [
        {'modelo': m, 'accion': a} for m, a in pares
    ]})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def rol_componentes(request, pk):
    """HU-SE02 regla 4: componentes de interfaz (visibles/editables) de un rol."""
    autorizar_acceso_modelo(request.user, 'rol')
    try:
        rol = Rol.objects.get(pk=pk)
    except Rol.DoesNotExist:
        return Response({'detail': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        if not _es_superadmin_usuario(request.user):
            colegio_id = _colegio_solicitante(request.user)
            if rol.colegio_id is not None and rol.colegio_id != colegio_id:
                return Response({'detail': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        componentes = PermisoComponenteSerializer(
            rol.componentes.all(), many=True,
        ).data
        return Response({'rol_id': rol.pk, 'componentes': componentes})

    rol = _rol_institucional_desde_admin(request, rol)

    if not _puede_gestionar_rol(request, rol) or not _gestion_puede(request):
        return _respuesta_no_autorizado()

    serializer = RolComponentesPayloadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    componentes = serializer.validated_data['componentes']

    with transaction.atomic():
        rol.componentes.all().delete()
        filas = [
            PermisoComponente(
                rol=rol, componente=item['componente'],
                visible=item['visible'], editable=item['editable'],
            )
            for item in componentes
        ]
        PermisoComponente.objects.bulk_create(filas)

    registrar_evento(
        accion='ACTUALIZAR', entidad='PERMISO_COMPONENTE', request=request,
        entidad_id=rol.pk, colegio=rol.colegio,
        cambios={'campos': ['componentes'], 'resultado': f'{len(componentes)} componentes'},
    )
    return Response({'rol_id': rol.pk, 'componentes': PermisoComponenteSerializer(
        rol.componentes.all(), many=True,
    ).data})


def _normalizar_puesto(nombre):
    import unicodedata
    return ''.join(
        caracter for caracter in unicodedata.normalize('NFD', nombre.casefold())
        if unicodedata.category(caracter) != 'Mn'
    ).strip()


def _director_institucional(request):
    admin = getattr(request.user, 'admin', None)
    if admin is None or _normalizar_puesto(getattr(admin.puesto, 'nombre', '')) != 'director':
        return None
    return admin


def _configuracion_institucional_payload(request, puesto, unidad, rol):
    propios = set(permisos_funcionales(request.user) or set())
    asignados = set(
        rol.permisos.select_related('modelo', 'accion').values_list('modelo__nombre', 'accion__nombre')
    ) if rol is not None else set()
    catalogo = {
        (modelo.nombre, accion.nombre)
        for modelo in ModeloPermitido.objects.all()
        for accion in Accion.objects.all()
    }
    metadatos = []
    for par in sorted(catalogo):
        disponible = par in propios
        metadatos.append({
            'modelo': par[0], 'accion': par[1],
            'directo': par in asignados, 'heredado': False,
            'disponible': disponible, 'bloqueado': not disponible,
            'motivo_bloqueo': None if disponible else 'Supera el techo de privilegios del Director.',
        })
    return {
        'rol_id': rol.pk if rol else None,
        'rol': RolSerializer(rol).data if rol else None,
        'perfil_objetivo': {'id': puesto.pk, 'nombre': puesto.nombre},
        'alcance': 'UNIDAD' if unidad else 'COLEGIO',
        'colegio_id': getattr(request.user.admin, 'colegio_id', None),
        'unidad': {'id': unidad.pk, 'nombre': unidad.nombre} if unidad else None,
        'permisos': [{'modelo': m, 'accion': a} for m, a in sorted(asignados)],
        'permisos_disponibles': [{'modelo': m, 'accion': a} for m, a in sorted(propios)],
        'permisos_heredados': [],
        'permisos_bloqueados': [item for item in metadatos if item['bloqueado']],
        'metadatos': metadatos,
        'puede_editar': True,
    }


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def configuracion_institucional(request):
    """Configura el rol funcional asociado a un puesto subordinado del Director."""
    autorizar_acceso_modelo(request.user, 'rol')
    admin = _director_institucional(request)
    if admin is None:
        return _respuesta_no_autorizado()
    puesto_id = request.data.get('puesto_id') if request.method == 'PUT' else request.query_params.get('puesto_id')
    if not puesto_id:
        puesto_id = Puesto.objects.exclude(nombre__iexact='Director').exclude(nombre__iexact='SuperAdmin').order_by('nombre').values_list('pk', flat=True).first()
    try:
        puesto = Puesto.objects.get(pk=puesto_id)
    except (Puesto.DoesNotExist, TypeError, ValueError):
        return Response({'detail': 'El perfil institucional no existe.'}, status=400)
    if _normalizar_puesto(puesto.nombre) in {'director', 'superadmin'}:
        return Response({'detail': 'No puede configurar este perfil institucional.'}, status=403)

    unidad_id = request.data.get('unidad_id') if request.method == 'PUT' else request.query_params.get('unidad_id')
    unidad = None
    if unidad_id not in (None, '', 'null'):
        from aplicaciones.institucion.models import UnidadEducativa
        unidad = UnidadEducativa.objects.filter(pk=unidad_id, colegio_id=admin.colegio_id).first()
        if unidad is None:
            return Response({'detail': 'La unidad no pertenece a su colegio.'}, status=403)

    rol = Rol.objects.filter(
        categoria=Rol.Categoria.FUNCIONAL, colegio_id=admin.colegio_id,
        puesto_id=puesto.pk, unidad_educativa_id=unidad.pk if unidad else None,
    ).select_related('colegio', 'unidad_educativa', 'puesto').first()
    if request.method == 'GET':
        return Response(_configuracion_institucional_payload(request, puesto, unidad, rol))

    pares = request.data.get('permisos', [])
    serializer = RolPermisosPayloadSerializer(data={'permisos': pares})
    serializer.is_valid(raise_exception=True)
    pares = serializer.validated_data['permisos']
    denegados = validar_no_escalacion(request.user, pares)
    if denegados:
        return Response({'detail': 'No puede conceder permisos que usted no posee: ' + ', '.join(f'{m}.{a}' for m, a in denegados) + '.'}, status=403)
    dependientes = {'crear', 'editar', 'desactivar', 'eliminar', 'descargar', 'generar', 'aprobar'}
    bases = {modelo for modelo, accion in pares if accion in {'listar', 'ver'}}
    incoherentes = sorted({modelo for modelo, accion in pares if accion in dependientes and modelo not in bases})
    if incoherentes:
        return Response({'detail': 'Cada permiso dependiente requiere listar o ver: ' + ', '.join(incoherentes) + '.'}, status=400)

    from aplicaciones.institucion.models import Colegio
    with transaction.atomic():
        Colegio.objects.select_for_update().get(pk=admin.colegio_id)
        rol = Rol.objects.select_for_update().filter(
            categoria=Rol.Categoria.FUNCIONAL, colegio_id=admin.colegio_id,
            puesto_id=puesto.pk, unidad_educativa_id=unidad.pk if unidad else None,
        ).first()
        if rol is None:
            base = puesto.nombre.strip()
            nombre = base if unidad is None else f'{base} · {unidad.nombre}'
            rol = Rol.objects.create(
                nombre=nombre[:50], descripcion=f'Configuración institucional de {puesto.nombre}',
                colegio_id=admin.colegio_id, unidad_educativa=unidad,
                puesto=puesto, categoria=Rol.Categoria.FUNCIONAL, activo=True,
            )
        rol.permisos.all().delete()
        modelos = {m.nombre: m for m in ModeloPermitido.objects.filter(nombre__in={p[0] for p in pares})}
        acciones = {a.nombre: a for a in Accion.objects.filter(nombre__in={p[1] for p in pares})}
        PermisoRol.objects.bulk_create([
            PermisoRol(rol=rol, modelo=modelos[m], accion=acciones[a]) for m, a in pares
        ])
    registrar_evento(
        accion='ACTUALIZAR', entidad='CONFIGURACION_INSTITUCIONAL', request=request,
        entidad_id=rol.pk, colegio=rol.colegio,
        cambios={'puesto': puesto.nombre, 'unidad': unidad.nombre if unidad else None, 'cantidad_permisos': len(pares)},
    )
    rol.refresh_from_db()
    return Response(_configuracion_institucional_payload(request, puesto, unidad, rol))


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def asignar_roles_usuario(request, pk):
    """HU-SE02 regla 5: roles adicionales de un usuario (uno o varios)."""
    autorizar_acceso_modelo(request.user, 'usuario')
    if not _puede(request, 'usuario'):
        return _respuesta_no_autorizado()
    if request.method == 'PUT' and not _es_director(request):
        return _respuesta_no_autorizado()
    try:
        usuario = Usuario.objects.select_related('rol', 'unidad', 'unidad__colegio').get(pk=pk)
    except Usuario.DoesNotExist:
        return Response({'detail': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _es_superadmin_usuario(request.user):
        try:
            validar_unidad(request.user, usuario.unidad)
        except Exception as exc:
            return Response({'detail': str(exc.detail)}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        return Response({
            'usuario_id': usuario.pk,
            'roles': [
                {'id': rol.pk, 'nombre': rol.nombre}
                for rol in usuario.roles_extras.filter(activo=True).order_by('nombre')
            ],
        })

    serializer = AsignarRolesSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    roles_destino = serializer.validated_data['rol_ids']

    colegio_destino = None
    if usuario.unidad_id and usuario.unidad.colegio_id:
        colegio_destino = usuario.unidad.colegio_id
    elif hasattr(usuario, 'admin') and usuario.admin.colegio_id:
        colegio_destino = usuario.admin.colegio_id

    for rol in roles_destino:
        if not _es_superadmin_usuario(request.user):
            colegio_solicitante = _colegio_solicitante(request.user)
            if not rol_asignable(
                rol,
                colegio_solicitante or colegio_destino,
                usuario.unidad_id,
            ):
                return Response(
                    {'detail': (
                        f'El rol "{rol.nombre}" no es asignable en su colegio '
                        '(debe estar activo y pertenecer al mismo tenant).'
                    )},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif not rol_asignable(rol):
            return Response(
                {'detail': (
                    f'El rol "{rol.nombre}" no es asignable (debe ser un rol '
                    'personalizado activo).'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

    denegados = roles_no_delegables(request.user, roles_destino)
    if denegados:
        nombres = ', '.join(rol.nombre for rol in denegados)
        return Response(
            {'detail': (
                'No puede asignar roles con privilegios superiores a los suyos: '
                + nombres + '.'
            )},
            status=status.HTTP_403_FORBIDDEN,
        )

    usuario.roles_extras.set(roles_destino)
    colegio_evento = None
    if usuario.unidad_id and usuario.unidad.colegio_id:
        colegio_evento = usuario.unidad.colegio
    elif hasattr(usuario, 'admin') and usuario.admin.colegio_id:
        colegio_evento = usuario.admin.colegio
    registrar_evento(
        accion='ACTUALIZAR', entidad='ASIGNACION_ROLES', request=request,
        entidad_id=usuario.pk, colegio=colegio_evento,
        cambios={'campos': ['roles_extras'], 'resultado': f'{len(roles_destino)} roles'},
    )
    return Response({
        'usuario_id': usuario.pk,
        'roles': [
            {'id': rol.pk, 'nombre': rol.nombre}
            for rol in usuario.roles_extras.filter(activo=True).order_by('nombre')
        ],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def acciones_catalogo(request):
    """Catálogo de acciones funcionales para la matriz de permisos."""
    if not (_es_superadmin_usuario(request.user) or hasattr(request.user, 'admin')):
        return _respuesta_no_autorizado()
    queryset = Accion.objects.all().order_by('nombre')
    return Response(AccionSerializer(queryset, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def modelos_catalogo(request):
    """Catálogo de modelos permitidos para la matriz de permisos."""
    if not (_es_superadmin_usuario(request.user) or hasattr(request.user, 'admin')):
        return _respuesta_no_autorizado()
    queryset = ModeloPermitido.objects.all().order_by('nombre')
    return Response(ModeloPermitidoSerializer(queryset, many=True).data)

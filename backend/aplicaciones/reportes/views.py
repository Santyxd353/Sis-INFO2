import uuid
from hashlib import sha256

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core import signing
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.usuarios.auditoria import registrar_evento
from aplicaciones.usuarios.tenancy import normalizar_nombre, resolver_alcance
from .especificacion import validar_especificacion
from .exportacion import exportar_csv, exportar_pdf, nombre_seguro
from .fuentes import catalogo_publico
from .fuentes_operativas import _REGISTRO, _esquema, ejecutar_fuente
from .models import EjecucionReporte, ReporteDefinicion
from .qbe import catalogo_qbe, ejecutar_qbe, validar_qbe, fuente_qbe, autorizar_columnas_estudiante, validar_puestos_alcance
from .seguridad import tiene_permiso
from .almacenamiento import almacenamiento, eliminar_archivo, guardar_archivo, validar_clave


def autorizar(user, recurso, accion):
    alcance = resolver_alcance(user)
    puesto = normalizar_nombre(getattr(getattr(getattr(user, 'admin', None), 'puesto', None), 'nombre', ''))
    if alcance['tipo'] not in ('COLEGIO', 'UNIDAD') or puesto not in ('director', 'secretaria') or not tiene_permiso(user, recurso, accion):
        raise PermissionDenied('Permiso o contexto no autorizado.')
    return alcance


def fuentes():
    return {f['codigo']: f for f in catalogo_publico()}


def validar_spec(codigo, especificacion):
    if codigo not in _REGISTRO:
        raise ValidationError({'codigo_fuente': 'Fuente no permitida.'})
    try:
        return validar_especificacion(especificacion, _esquema(_REGISTRO[codigo]))
    except DjangoValidationError as exc:
        raise ValidationError({'especificacion': getattr(exc, 'message_dict', exc.messages)}) from exc


def validar_qbe_spec(codigo, especificacion):
    fuente = fuente_qbe(codigo) if isinstance(codigo, str) else None
    if fuente is None:
        raise ValidationError({'codigo_fuente': 'Fuente QBE no permitida.'})
    try:
        return validar_qbe(especificacion, fuente)
    except DjangoValidationError as exc:
        raise ValidationError({'especificacion': getattr(exc, 'message_dict', exc.messages)}) from exc


def validar_puestos(user, codigo, spec):
    try:
        validar_puestos_alcance(user, codigo, spec)
    except DjangoValidationError as exc:
        raise ValidationError({'especificacion': {'condiciones': exc.messages}}) from exc


def propias(user, alcance):
    consulta = ReporteDefinicion.objects.filter(propietario=user, colegio_id=alcance['colegio_id'], tipo='OPERATIVO').select_related('colegio', 'unidad_educativa')
    if alcance['tipo'] == 'UNIDAD':
        consulta = consulta.filter(unidad_educativa_id=alcance['unidad_id'])
    return consulta


def propias_qbe(user, alcance):
    consulta = ReporteDefinicion.objects.filter(propietario=user, colegio_id=alcance['colegio_id'], tipo='QBE').select_related('colegio', 'unidad_educativa')
    return consulta.filter(unidad_educativa_id=alcance['unidad_id']) if alcance['tipo'] == 'UNIDAD' else consulta


def autorizar_qbe(user, accion):
    alcance = resolver_alcance(user)
    puesto = normalizar_nombre(getattr(getattr(getattr(user, 'admin', None), 'puesto', None), 'nombre', ''))
    if puesto not in ('director', 'secretaria') or alcance['tipo'] not in ('COLEGIO', 'UNIDAD') or not tiene_permiso(user, 'reporte-qbe', accion):
        raise PermissionDenied('Permiso QBE no autorizado.')
    return alcance


def serializar(obj):
    return {'id': obj.pk, 'nombre': obj.nombre, 'tipo': obj.tipo,
            'codigo_fuente': obj.codigo_fuente, 'nombre_fuente': (fuente_qbe(obj.codigo_fuente) or {}).get('nombre'),
            'descripcion': obj.descripcion,
            'version_esquema': obj.version_esquema, 'especificacion': obj.especificacion,
            'estado': obj.estado, 'colegio': obj.colegio_id, 'unidad_educativa': obj.unidad_educativa_id,
            'propietario': obj.propietario_id, 'created_at': obj.created_at,
            'updated_at': obj.updated_at, 'archivado_at': obj.archivado_at}


def contar_condiciones(nodo):
    if not isinstance(nodo, dict):
        return 0
    return 1 if 'campo' in nodo else sum(contar_condiciones(hijo) for hijo in nodo.get('condiciones', []))


def auditar(request, obj, accion, entidad='REPORTE_DEFINICION', cantidad=None, correlacion=None):
    cambios = {'fuente': obj.fuente_codigo if entidad == 'REPORTE_EJECUCION' else obj.codigo_fuente}
    if entidad == 'REPORTE_EJECUCION':
        cambios['estado'] = obj.estado
    if obj.tipo == 'QBE':
        spec = obj.definicion.especificacion if entidad == 'REPORTE_EJECUCION' and obj.definicion_id else (obj.especificacion if entidad == 'REPORTE_DEFINICION' else {})
        if entidad == 'REPORTE_EJECUCION':
            cambios['formato'] = obj.formato
            cambios['definicion_id'] = obj.definicion_id
            cambios['columnas'] = obj.parametros_sanitizados.get('columnas', [])
        else:
            cambios['columnas'] = spec.get('columnas', [])
        cantidad_condiciones = contar_condiciones(spec.get('condiciones', {})) if spec else obj.parametros_sanitizados.get('cantidad_condiciones', 0)
        cambios['campos'] = [f'columna:{campo}' for campo in cambios['columnas']]
        cambios['campos'].append(f'condiciones:{cantidad_condiciones}')
        if entidad == 'REPORTE_EJECUCION':
            cambios['campos'].append(f'formato:{obj.formato}')
            if obj.definicion_id:
                cambios['campos'].append(f'definicion:{obj.definicion_id}')
    if accion == 'DESCARGAR':
        cambios['operacion'] = 'DESCARGA_HISTORIAL'
        accion = 'EXPORTAR'
    if cantidad is not None:
        cambios['cantidad_filas'] = cantidad
    registrar_evento(accion=accion, entidad=entidad, entidad_id=obj.pk, request=request,
                     colegio=obj.colegio, unidad=obj.unidad_educativa, cambios=cambios,
                     correlacion=correlacion or uuid.uuid4(), inferir_unidad=False)


def guardar(obj):
    try:
        obj.save()
    except DjangoValidationError as exc:
        raise ValidationError(getattr(exc, 'message_dict', exc.messages)) from exc
    except IntegrityError as exc:
        raise ValidationError('La definición entra en conflicto con un registro existente.') from exc


def validar_entrada(data, permitidos):
    if not isinstance(data, dict) or set(data) - permitidos:
        raise ValidationError('Hay campos no permitidos.')


class Base(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class Catalogo(Base):
    def get(self, request, codigo=None):
        autorizar(request.user, 'reporte-definicion', 'listar')
        items = fuentes()
        if codigo is not None:
            if codigo not in items:
                return Response(status=404)
            return Response(items[codigo])
        paginator = PageNumberPagination()
        paginator.page_size = 20
        return paginator.get_paginated_response(paginator.paginate_queryset(list(items.values()), request, view=self))


class Definiciones(Base):
    def get(self, request):
        alcance = autorizar(request.user, 'reporte-definicion', 'listar')
        paginator = PageNumberPagination()
        paginator.page_size = 20
        pagina = paginator.paginate_queryset(propias(request.user, alcance).order_by('pk'), request, view=self)
        return paginator.get_paginated_response([serializar(obj) for obj in pagina])

    def post(self, request):
        alcance = autorizar(request.user, 'reporte-definicion', 'crear')
        validar_entrada(request.data, {'nombre', 'codigo_fuente', 'unidad_educativa', 'especificacion'})
        if not all(k in request.data for k in ('nombre', 'codigo_fuente', 'especificacion')):
            raise ValidationError('Faltan campos requeridos.')
        if not isinstance(request.data['nombre'], str) or not isinstance(request.data['codigo_fuente'], str):
            raise ValidationError('Nombre y código deben ser texto.')
        if alcance['tipo'] == 'UNIDAD' and 'unidad_educativa' in request.data:
            raise ValidationError({'unidad_educativa': 'La unidad se deriva del perfil.'})
        unidad_id = alcance['unidad_id'] if alcance['tipo'] == 'UNIDAD' else request.data.get('unidad_educativa')
        unidad = None
        if unidad_id is not None:
            try:
                unidad = UnidadEducativa.objects.filter(pk=unidad_id, colegio_id=alcance['colegio_id']).first()
            except (ValueError, TypeError):
                unidad = None
            if unidad is None:
                raise ValidationError({'unidad_educativa': 'Unidad fuera del colegio.'})
        spec = validar_spec(request.data['codigo_fuente'], request.data['especificacion'])
        obj = ReporteDefinicion(colegio_id=alcance['colegio_id'], unidad_educativa=unidad,
                                propietario=request.user, nombre=request.data['nombre'], tipo='OPERATIVO',
                                codigo_fuente=request.data['codigo_fuente'], version_esquema=1, especificacion=spec)
        with transaction.atomic():
            guardar(obj)
            auditar(request, obj, 'CREAR')
        return Response(serializar(obj), status=status.HTTP_201_CREATED)


class DefinicionDetalle(Base):
    def get(self, request, pk):
        alcance = autorizar(request.user, 'reporte-definicion', 'listar')
        return Response(serializar(get_object_or_404(propias(request.user, alcance), pk=pk)))

    def patch(self, request, pk):
        alcance = autorizar(request.user, 'reporte-definicion', 'editar')
        validar_entrada(request.data, {'nombre', 'especificacion'})
        with transaction.atomic():
            obj = get_object_or_404(propias(request.user, alcance).select_for_update(of=('self',)), pk=pk)
            if obj.estado != 'ACTIVO':
                raise ValidationError('La definición está archivada.')
            if 'nombre' in request.data:
                if not isinstance(request.data['nombre'], str):
                    raise ValidationError({'nombre': 'Debe ser texto.'})
                obj.nombre = request.data['nombre']
            if 'especificacion' in request.data:
                obj.especificacion = validar_spec(obj.codigo_fuente, request.data['especificacion'])
            guardar(obj)
            auditar(request, obj, 'ACTUALIZAR')
        return Response(serializar(obj))


class Archivar(Base):
    def post(self, request, pk):
        alcance = autorizar(request.user, 'reporte-definicion', 'archivar')
        validar_entrada(request.data, set())
        with transaction.atomic():
            obj = get_object_or_404(propias(request.user, alcance).select_for_update(of=('self',)), pk=pk)
            if obj.estado != 'ARCHIVADO':
                obj.estado = 'ARCHIVADO'
                obj.archivado_at = timezone.now()
                guardar(obj)
                auditar(request, obj, 'ARCHIVAR')
        return Response(serializar(obj))


class Previsualizar(Base):
    def post(self, request):
        alcance = autorizar(request.user, 'reporte-ejecucion', 'ejecutar')
        validar_entrada(request.data, {'definicion_id'})
        campo = serializers.IntegerField(min_value=1)
        pk = campo.run_validation(request.data.get('definicion_id'))
        with transaction.atomic():
            obj = get_object_or_404(propias(request.user, alcance).select_for_update(of=('self',)), pk=pk, estado='ACTIVO')
            spec = validar_spec(obj.codigo_fuente, obj.especificacion)
            correlacion = uuid.uuid4()
            ejecucion = EjecucionReporte(definicion=obj, colegio=obj.colegio, unidad_educativa=obj.unidad_educativa,
                solicitante=request.user, actor_snapshot={'usuario_id': request.user.pk}, tipo='OPERATIVO',
                fuente_codigo=obj.codigo_fuente, fuente_version=obj.version_esquema, formato='JSON',
                parametros_sanitizados={}, correlacion=correlacion)
            guardar(ejecucion)
            ejecucion.estado = 'EN_PROCESO'
            guardar(ejecucion)
            try:
                with transaction.atomic():
                    spec, filas, limitado = ejecutar_fuente(request.user, obj.codigo_fuente, spec, unidad_id=obj.unidad_educativa_id)
            except Exception:
                ejecucion.estado = 'ERROR'
                ejecucion.error_sanitizado = 'ERROR_PREVISUALIZACION'
                ejecucion.finalizada_at = timezone.now()
                guardar(ejecucion)
                auditar(request, ejecucion, 'REPORTAR', 'REPORTE_EJECUCION', 0, correlacion)
                return Response({'detail': 'No se pudo generar la previsualización.', 'ejecucion_id': ejecucion.pk}, status=400)
            ejecucion.estado = 'COMPLETADO'
            ejecucion.filas_resultado = len(filas)
            ejecucion.finalizada_at = timezone.now()
            guardar(ejecucion)
            auditar(request, ejecucion, 'REPORTAR', 'REPORTE_EJECUCION', len(filas), correlacion)
            fuente = fuentes()[obj.codigo_fuente]
            columnas = {c['campo']: c for c in fuente['columnas']}
            return Response({'ejecucion_id': ejecucion.pk, 'fuente': {k: fuente[k] for k in ('codigo', 'nombre', 'version')},
                'alcance': {'colegio': {'id': obj.colegio_id, 'nombre': obj.colegio.nombre},
                            'unidad': {'id': obj.unidad_educativa_id, 'nombre': obj.unidad_educativa.nombre} if obj.unidad_educativa else None},
                'fecha_generacion': ejecucion.finalizada_at, 'columnas': [{'campo': c, 'etiqueta': columnas[c]['etiqueta']} for c in spec['columnas']],
                'filas': filas, 'cantidad': len(filas), 'limite': 100, 'limite_alcanzado': limitado})


class Exportar(Base):
    """Genera y guarda una exportación privada."""
    limite_filas = 5000
    limite_bytes = 10 * 1024 * 1024

    def post(self, request):
        alcance = autorizar(request.user, 'reporte-ejecucion', 'descargar')
        validar_entrada(request.data, {'definicion_id', 'formato'})
        pk = serializers.IntegerField(min_value=1).run_validation(request.data.get('definicion_id'))
        formato = request.data.get('formato')
        if formato not in ('CSV', 'PDF'):
            raise ValidationError({'formato': 'Seleccione CSV o PDF.'})
        with transaction.atomic():
            definicion = get_object_or_404(
                propias(request.user, alcance).select_for_update(of=('self',)), pk=pk, estado='ACTIVO',
            )
            spec = validar_spec(definicion.codigo_fuente, definicion.especificacion)
            correlacion = uuid.uuid4()
            ejecucion = EjecucionReporte(
                definicion=definicion, colegio=definicion.colegio, unidad_educativa=definicion.unidad_educativa,
                solicitante=request.user, actor_snapshot={'usuario_id': request.user.pk}, tipo='OPERATIVO',
                fuente_codigo=definicion.codigo_fuente, fuente_version=definicion.version_esquema,
                formato=formato, parametros_sanitizados={'columnas': spec['columnas']},
                correlacion=correlacion,
            )
            guardar(ejecucion)
            ejecucion.estado = 'EN_PROCESO'
            guardar(ejecucion)
            try:
                _, filas, limitado = ejecutar_fuente(
                    request.user, definicion.codigo_fuente, spec, limite=self.limite_filas,
                    unidad_id=definicion.unidad_educativa_id,
                )
                if limitado:
                    raise ValueError('LIMITE_EXPORTACION')
                fuente = fuentes()[definicion.codigo_fuente]
                columnas = {columna['campo']: columna for columna in fuente['columnas']}
                encabezados = [columnas[campo]['etiqueta'] for campo in spec['columnas']]
                if formato == 'CSV':
                    contenido, mime, extension = exportar_csv(encabezados, filas)
                else:
                    contenido, mime, extension = exportar_pdf(fuente['nombre'], encabezados, filas)
                if len(contenido) > self.limite_bytes:
                    raise ValueError('TAMANO_EXPORTACION')
                ejecucion.archivo_referencia = guardar_archivo(contenido, extension)
            except Exception:
                ejecucion.estado = 'ERROR'
                ejecucion.error_sanitizado = 'ERROR_EXPORTACION'
                ejecucion.finalizada_at = timezone.now()
                guardar(ejecucion)
                auditar(request, ejecucion, 'EXPORTAR', 'REPORTE_EJECUCION', 0, correlacion)
                return Response({'detail': 'No se pudo generar la exportación.', 'ejecucion_id': ejecucion.pk}, status=400)
            ejecucion.estado = 'COMPLETADO'
            ejecucion.filas_resultado = len(filas)
            ejecucion.archivo_mime = mime
            ejecucion.archivo_tamano = len(contenido)
            ejecucion.archivo_checksum = sha256(contenido).hexdigest()
            ejecucion.finalizada_at = timezone.now()
            try:
                with transaction.atomic():
                    guardar(ejecucion)
                    auditar(request, ejecucion, 'EXPORTAR', 'REPORTE_EJECUCION', len(filas), correlacion)
            except Exception:
                eliminar_archivo(ejecucion.archivo_referencia)
                ejecucion.archivo_referencia = None
                ejecucion.estado = 'ERROR'
                ejecucion.error_sanitizado = 'ERROR_EXPORTACION'
                guardar(ejecucion)
                auditar(request, ejecucion, 'EXPORTAR', 'REPORTE_EJECUCION', 0, correlacion)
                return Response({'detail': 'No se pudo generar la exportación.', 'ejecucion_id': ejecucion.pk}, status=400)
        respuesta = HttpResponse(contenido, content_type=mime)
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre_seguro(definicion.nombre, extension)}"'
        respuesta['X-Reporte-Ejecucion'] = str(ejecucion.pk)
        return respuesta


class QbeCatalogo(Base):
    def get(self, request, codigo=None):
        autorizar_qbe(request.user, 'validar')
        items = {item['codigo']: item for item in catalogo_qbe(request.user)}
        if codigo is not None:
            return Response(items[codigo]) if codigo in items else Response(status=404)
        return Response({'count': len(items), 'results': list(items.values())})


class QbeDefiniciones(Base):
    def get(self, request):
        alcance = autorizar_qbe(request.user, 'validar')
        paginator = PageNumberPagination()
        paginator.page_size = 20
        pagina = paginator.paginate_queryset(propias_qbe(request.user, alcance).filter(estado='ACTIVO').order_by('pk'), request, view=self)
        return paginator.get_paginated_response([serializar(item) for item in pagina])

    def post(self, request):
        alcance = autorizar_qbe(request.user, 'validar')
        autorizar(request.user, 'reporte-definicion', 'crear')
        validar_entrada(request.data, {'nombre', 'codigo_fuente', 'especificacion'})
        if not all(campo in request.data for campo in ('nombre', 'codigo_fuente', 'especificacion')):
            raise ValidationError('Faltan campos requeridos.')
        if not isinstance(request.data['codigo_fuente'], str) or fuente_qbe(request.data['codigo_fuente']) is None or not isinstance(request.data['nombre'], str):
            raise ValidationError('Fuente o nombre inválido.')
        spec = validar_qbe_spec(request.data['codigo_fuente'], request.data['especificacion'])
        autorizar_columnas_estudiante(request.user, request.data['codigo_fuente'], spec['columnas'])
        validar_puestos(request.user, request.data['codigo_fuente'], spec)
        unidad_id = alcance['unidad_id'] if alcance['tipo'] == 'UNIDAD' else None
        obj = ReporteDefinicion(colegio_id=alcance['colegio_id'], unidad_educativa_id=unidad_id,
                                propietario=request.user, nombre=request.data['nombre'], tipo='QBE',
                                codigo_fuente=request.data['codigo_fuente'], version_esquema=1, especificacion=spec)
        with transaction.atomic():
            guardar(obj); auditar(request, obj, 'CREAR')
        return Response(serializar(obj), status=status.HTTP_201_CREATED)


class QbeDefinicionDetalle(Base):
    def get(self, request, pk):
        alcance = autorizar_qbe(request.user, 'validar')
        return Response(serializar(get_object_or_404(propias_qbe(request.user, alcance), pk=pk)))

    def patch(self, request, pk):
        alcance = autorizar_qbe(request.user, 'validar')
        autorizar(request.user, 'reporte-definicion', 'editar')
        validar_entrada(request.data, {'nombre', 'especificacion'})
        with transaction.atomic():
            obj = get_object_or_404(propias_qbe(request.user, alcance).select_for_update(of=('self',)), pk=pk, estado='ACTIVO')
            if 'nombre' in request.data:
                if not isinstance(request.data['nombre'], str):
                    raise ValidationError({'nombre': 'Debe ser texto.'})
                obj.nombre = request.data['nombre']
            if 'especificacion' in request.data:
                obj.especificacion = validar_qbe_spec(obj.codigo_fuente, request.data['especificacion'])
                autorizar_columnas_estudiante(request.user, obj.codigo_fuente, obj.especificacion['columnas'])
                validar_puestos(request.user, obj.codigo_fuente, obj.especificacion)
            guardar(obj)
            auditar(request, obj, 'ACTUALIZAR')
        return Response(serializar(obj))


class QbeArchivar(Base):
    def post(self, request, pk):
        alcance = autorizar_qbe(request.user, 'validar')
        autorizar(request.user, 'reporte-definicion', 'archivar')
        validar_entrada(request.data, set())
        with transaction.atomic():
            obj = get_object_or_404(propias_qbe(request.user, alcance).select_for_update(of=('self',)), pk=pk)
            if obj.estado != 'ARCHIVADO':
                obj.estado = 'ARCHIVADO'
                obj.archivado_at = timezone.now()
                guardar(obj)
                auditar(request, obj, 'ARCHIVAR')
        return Response(serializar(obj))


class QbePrevisualizar(Base):
    def post(self, request):
        alcance = autorizar_qbe(request.user, 'ejecutar')
        validar_entrada(request.data, {'definicion_id', 'codigo_fuente', 'especificacion'})
        if 'definicion_id' not in request.data:
            if set(request.data) != {'codigo_fuente', 'especificacion'}:
                raise ValidationError('Se requiere una fuente y una especificación.')
            codigo = request.data['codigo_fuente']
            spec = validar_qbe_spec(codigo, request.data['especificacion'])
            autorizar_columnas_estudiante(request.user, codigo, spec['columnas'])
            validar_puestos(request.user, codigo, spec)
            correlacion = uuid.uuid4()
            with transaction.atomic():
                ejecucion = EjecucionReporte(colegio_id=alcance['colegio_id'], unidad_educativa_id=alcance['unidad_id'] if alcance['tipo'] == 'UNIDAD' else None,
                    solicitante=request.user, actor_snapshot={'usuario_id': request.user.pk}, tipo='QBE', fuente_codigo=codigo,
                    formato='JSON', parametros_sanitizados={'columnas': spec['columnas'], 'cantidad_condiciones': contar_condiciones(spec['condiciones'])}, correlacion=correlacion)
                guardar(ejecucion)
                try:
                    _, filas, limitado = ejecutar_qbe(request.user, codigo, spec, unidad_id=ejecucion.unidad_educativa_id)
                except Exception:
                    ejecucion.estado = 'ERROR'; ejecucion.error_sanitizado = 'ERROR_QBE'; ejecucion.finalizada_at = timezone.now(); guardar(ejecucion)
                    auditar(request, ejecucion, 'CONSULTAR_QBE', 'REPORTE_EJECUCION', 0, correlacion)
                    return Response({'detail': 'No se pudo ejecutar la consulta.'}, status=400)
                ejecucion.estado = 'COMPLETADO'; ejecucion.filas_resultado = len(filas); ejecucion.finalizada_at = timezone.now(); guardar(ejecucion)
                auditar(request, ejecucion, 'CONSULTAR_QBE', 'REPORTE_EJECUCION', len(filas), correlacion)
            columnas = {item['campo']: item for item in {x['codigo']: x for x in catalogo_qbe()}[codigo]['columnas']}
            return Response({'ejecucion_id': ejecucion.pk, 'columnas': [{'campo': campo, 'etiqueta': columnas[campo]['etiqueta']} for campo in spec['columnas']], 'filas': filas, 'cantidad': len(filas), 'limite': min(100, spec.get('limite', 100)), 'limite_alcanzado': limitado, 'orden': spec['orden'], 'resumen': f"Consulta de {len(spec['columnas'])} columnas."})
        if set(request.data) != {'definicion_id'}:
            raise ValidationError('Seleccione una definición o una especificación.')
        pk = serializers.IntegerField(min_value=1).run_validation(request.data.get('definicion_id'))
        with transaction.atomic():
            obj = get_object_or_404(propias_qbe(request.user, alcance).select_for_update(of=('self',)), pk=pk, estado='ACTIVO')
            spec = validar_qbe_spec(obj.codigo_fuente, obj.especificacion)
            autorizar_columnas_estudiante(request.user, obj.codigo_fuente, spec['columnas'])
            validar_puestos(request.user, obj.codigo_fuente, spec)
            correlacion = uuid.uuid4()
            ejecucion = EjecucionReporte(definicion=obj, colegio=obj.colegio, unidad_educativa=obj.unidad_educativa,
                solicitante=request.user, actor_snapshot={'usuario_id': request.user.pk}, tipo='QBE', fuente_codigo=obj.codigo_fuente,
                fuente_version=obj.version_esquema, formato='JSON', parametros_sanitizados={'columnas': spec['columnas']}, correlacion=correlacion)
            guardar(ejecucion); ejecucion.estado = 'EN_PROCESO'; guardar(ejecucion)
            try:
                _, filas, limitado = ejecutar_qbe(request.user, obj.codigo_fuente, spec, unidad_id=obj.unidad_educativa_id)
            except Exception:
                ejecucion.estado = 'ERROR'; ejecucion.error_sanitizado = 'ERROR_QBE'; ejecucion.finalizada_at = timezone.now(); guardar(ejecucion)
                auditar(request, ejecucion, 'CONSULTAR_QBE', 'REPORTE_EJECUCION', 0, correlacion)
                return Response({'detail': 'No se pudo ejecutar la consulta.', 'ejecucion_id': ejecucion.pk}, status=400)
            ejecucion.estado = 'COMPLETADO'; ejecucion.filas_resultado = len(filas); ejecucion.finalizada_at = timezone.now(); guardar(ejecucion)
            auditar(request, ejecucion, 'CONSULTAR_QBE', 'REPORTE_EJECUCION', len(filas), correlacion)
            columnas = {item['campo']: item for item in {x['codigo']: x for x in catalogo_qbe()}[obj.codigo_fuente]['columnas']}
            return Response({'ejecucion_id': ejecucion.pk, 'columnas': [{'campo': campo, 'etiqueta': columnas[campo]['etiqueta']} for campo in spec['columnas']], 'filas': filas, 'cantidad': len(filas), 'limite': min(100, spec.get('limite', 100)), 'limite_alcanzado': limitado, 'orden': spec['orden'], 'resumen': f"Consulta de {len(spec['columnas'])} columnas."})


class QbeExportar(Base):
    limite_filas = 5000
    limite_bytes = 10 * 1024 * 1024

    def post(self, request):
        alcance = autorizar_qbe(request.user, 'ejecutar')
        validar_entrada(request.data, {'definicion_id', 'formato'})
        pk = serializers.IntegerField(min_value=1).run_validation(request.data.get('definicion_id'))
        formato = request.data.get('formato')
        if formato not in ('CSV', 'PDF'):
            raise ValidationError({'formato': 'Seleccione CSV o PDF.'})
        with transaction.atomic():
            obj = get_object_or_404(propias_qbe(request.user, alcance).select_for_update(of=('self',)), pk=pk, estado='ACTIVO')
            spec = validar_qbe_spec(obj.codigo_fuente, obj.especificacion)
            autorizar_columnas_estudiante(request.user, obj.codigo_fuente, spec['columnas'])
            validar_puestos(request.user, obj.codigo_fuente, spec)
            correlacion = uuid.uuid4()
            ejecucion = EjecucionReporte(definicion=obj, colegio=obj.colegio, unidad_educativa=obj.unidad_educativa,
                solicitante=request.user, actor_snapshot={'usuario_id': request.user.pk}, tipo='QBE', fuente_codigo=obj.codigo_fuente,
                fuente_version=obj.version_esquema, formato=formato, parametros_sanitizados={'columnas': spec['columnas']}, correlacion=correlacion)
            guardar(ejecucion); ejecucion.estado = 'EN_PROCESO'; guardar(ejecucion)
            try:
                _, filas, limitado = ejecutar_qbe(request.user, obj.codigo_fuente, spec, limite=self.limite_filas, unidad_id=obj.unidad_educativa_id)
                if limitado and 'limite' not in spec:
                    raise ValueError('LIMITE_EXPORTACION')
                fuente = {item['codigo']: item for item in catalogo_qbe()}[obj.codigo_fuente]
                columnas = {item['campo']: item for item in fuente['columnas']}
                encabezados = [columnas[campo]['etiqueta'] for campo in spec['columnas']]
                contenido, mime, extension = exportar_csv(encabezados, filas) if formato == 'CSV' else exportar_pdf(fuente['etiqueta'], encabezados, filas)
                if len(contenido) > self.limite_bytes:
                    raise ValueError('TAMANO_EXPORTACION')
                ejecucion.archivo_referencia = guardar_archivo(contenido, extension)
            except Exception:
                ejecucion.estado = 'ERROR'; ejecucion.error_sanitizado = 'ERROR_QBE_EXPORTACION'; ejecucion.finalizada_at = timezone.now(); guardar(ejecucion)
                auditar(request, ejecucion, 'EXPORTAR', 'REPORTE_EJECUCION', 0, correlacion)
                return Response({'detail': 'No se pudo exportar la consulta.', 'ejecucion_id': ejecucion.pk}, status=400)
            ejecucion.estado = 'COMPLETADO'; ejecucion.filas_resultado = len(filas); ejecucion.archivo_mime = mime
            ejecucion.archivo_tamano = len(contenido); ejecucion.archivo_checksum = sha256(contenido).hexdigest(); ejecucion.finalizada_at = timezone.now()
            try:
                with transaction.atomic():
                    guardar(ejecucion)
                    auditar(request, ejecucion, 'EXPORTAR', 'REPORTE_EJECUCION', len(filas), correlacion)
            except Exception:
                eliminar_archivo(ejecucion.archivo_referencia)
                ejecucion.archivo_referencia = None
                ejecucion.estado = 'ERROR'
                ejecucion.error_sanitizado = 'ERROR_QBE_EXPORTACION'
                guardar(ejecucion)
                auditar(request, ejecucion, 'EXPORTAR', 'REPORTE_EJECUCION', 0, correlacion)
                return Response({'detail': 'No se pudo exportar la consulta.', 'ejecucion_id': ejecucion.pk}, status=400)
        respuesta = HttpResponse(contenido, content_type=mime)
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre_seguro(obj.nombre, extension)}"'
        respuesta['X-Reporte-Ejecucion'] = str(ejecucion.pk)
        return respuesta


def historial_autorizado(user, recurso='reporte-ejecucion', accion='listar'):
    alcance = autorizar(user, recurso, accion)
    queryset = EjecucionReporte.objects.filter(
        colegio_id=alcance['colegio_id'], formato__in=['CSV', 'PDF'], tipo__in=['OPERATIVO', 'QBE', 'ANALITICO'],
    ).select_related('definicion', 'unidad_educativa', 'solicitante', 'colegio')
    if alcance['tipo'] == 'UNIDAD':
        queryset = queryset.filter(unidad_educativa_id=alcance['unidad_id'])
    if not tiene_permiso(user, 'reporte-qbe', 'ejecutar'):
        queryset = queryset.exclude(tipo='QBE')
    if not tiene_permiso(user, 'reporte-analitico', 'listar'):
        queryset = queryset.exclude(tipo='ANALITICO')
    return queryset


def serializar_ejecucion(obj):
    return {
        'id': str(obj.pk), 'nombre': obj.definicion.nombre if obj.definicion else obj.fuente_codigo,
        'fuente': obj.fuente_codigo, 'fuente_nombre': (fuente_qbe(obj.fuente_codigo) or {}).get('nombre', obj.fuente_codigo), 'tipo': obj.tipo, 'formato': obj.formato,
        'estado': obj.estado, 'unidad_id': obj.unidad_educativa_id,
        'unidad': obj.unidad_educativa.nombre if obj.unidad_educativa else None,
        'ejecutor': str(obj.solicitante) if obj.solicitante else None,
        'iniciada_at': obj.iniciada_at, 'finalizada_at': obj.finalizada_at,
        'tamano': obj.archivo_tamano, 'archivado_at': obj.archivado_at,
    }


class Ejecuciones(Base):
    def get(self, request):
        consulta = historial_autorizado(request.user)
        permitidos = {'fuente', 'formato', 'estado', 'unidad', 'desde', 'hasta', 'archivados', 'page'}
        if set(request.query_params) - permitidos:
            raise ValidationError('Filtro no permitido.')
        params = request.query_params
        fuente = params.get('fuente')
        if fuente:
            if fuente_qbe(fuente) is None:
                raise ValidationError({'fuente': 'Fuente no válida.'})
            consulta = consulta.filter(fuente_codigo=fuente)
        for campo, valores in [('formato', ('CSV', 'PDF')), ('estado', ('PENDIENTE', 'EN_PROCESO', 'COMPLETADO', 'ERROR', 'CANCELADO'))]:
            valor = params.get(campo)
            if valor:
                if valor not in valores:
                    raise ValidationError({campo: 'Valor no válido.'})
                consulta = consulta.filter(**{campo: valor})
        if params.get('unidad'):
            unidad = serializers.IntegerField(min_value=1).run_validation(params['unidad'])
            consulta = consulta.filter(unidad_educativa_id=unidad)
        fechas = {}
        for campo in ('desde', 'hasta'):
            if params.get(campo):
                try:
                    fechas[campo] = parse_date(params[campo])
                except ValueError:
                    fechas[campo] = None
                if not fechas[campo]:
                    raise ValidationError({campo: 'Fecha no válida.'})
        if fechas.get('desde') and fechas.get('hasta') and fechas['desde'] > fechas['hasta']:
            raise ValidationError('El rango de fechas no es válido.')
        if fechas.get('desde'):
            consulta = consulta.filter(iniciada_at__date__gte=fechas['desde'])
        if fechas.get('hasta'):
            consulta = consulta.filter(iniciada_at__date__lte=fechas['hasta'])
        archivados = params.get('archivados', 'false')
        if archivados not in ('true', 'false'):
            raise ValidationError({'archivados': 'Valor no válido.'})
        if archivados == 'true':
            autorizar(request.user, 'reporte-definicion', 'archivar')
            consulta = consulta.filter(archivado_at__isnull=False)
        else:
            consulta = consulta.filter(archivado_at__isnull=True)
        paginator = PageNumberPagination()
        paginator.page_size = 20
        pagina = paginator.paginate_queryset(consulta.order_by('-iniciada_at', '-pk'), request, view=self)
        return paginator.get_paginated_response([serializar_ejecucion(obj) for obj in pagina])


class EjecucionDetalle(Base):
    def get(self, request, pk):
        obj = get_object_or_404(historial_autorizado(request.user), pk=pk)
        if obj.archivado_at:
            autorizar(request.user, 'reporte-definicion', 'archivar')
        return Response(serializar_ejecucion(obj))


class EjecucionDescargar(Base):
    def get(self, request, pk):
        obj = get_object_or_404(historial_autorizado(request.user, accion='descargar'), pk=pk, archivado_at__isnull=True)
        if obj.tipo == 'QBE':
            autorizar_columnas_estudiante(request.user, obj.fuente_codigo, obj.parametros_sanitizados.get('columnas', []))
        if obj.estado != 'COMPLETADO' or not obj.archivo_referencia:
            return Response({'detail': 'Archivo no disponible.'}, status=404)
        try:
            storage = almacenamiento()
            with storage.open(validar_clave(obj.archivo_referencia), 'rb') as archivo:
                contenido = archivo.read(Exportar.limite_bytes + 1)
            if len(contenido) > Exportar.limite_bytes or (obj.archivo_tamano is not None and len(contenido) != obj.archivo_tamano) or (obj.archivo_checksum and sha256(contenido).hexdigest() != obj.archivo_checksum):
                raise ValueError('Archivo inválido')
        except (OSError, ValueError):
            return Response({'detail': 'Archivo no disponible.'}, status=404)
        auditar(request, obj, 'DESCARGAR', 'REPORTE_EJECUCION')
        respuesta = HttpResponse(contenido, content_type=obj.archivo_mime or 'application/octet-stream')
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre_seguro(obj.definicion.nombre if obj.definicion else "reporte", obj.formato.lower())}"'
        respuesta['X-Content-Type-Options'] = 'nosniff'
        return respuesta


class EjecucionArchivar(Base):
    def post(self, request, pk):
        validar_entrada(request.data, set())
        with transaction.atomic():
            obj = get_object_or_404(historial_autorizado(request.user, 'reporte-definicion', 'archivar').select_for_update(of=('self',)), pk=pk)
            if not obj.archivado_at:
                obj.archivado_at = timezone.now()
                guardar(obj)
                auditar(request, obj, 'ARCHIVAR', 'REPORTE_EJECUCION')
        return Response(serializar_ejecucion(obj))


def auditar_analitica(request, unidad, accion, contexto, formato=None, ejecucion=None):
    campos = [f'{clave}:{valor}' for clave, valor in contexto.items() if valor is not None]
    campos.extend(['metrica:matricula_actual', 'metrica:rendimiento', 'metrica:asistencia', 'metrica:incidentes', 'series:6'])
    if formato:
        campos.append(f'formato:{formato}')
    registrar_evento(accion=accion, entidad='REPORTE_EJECUCION', entidad_id=ejecucion.pk if ejecucion else None,
        request=request, colegio=unidad.colegio, unidad=unidad, inferir_unidad=False,
        cambios={'fuente': 'ANALITICA', 'campos': campos}, correlacion=ejecucion.correlacion if ejecucion else uuid.uuid4())


class AnaliticaResumen(Base):
    def get(self, request):
        from .analitica import contexto, resumen
        alcance = autorizar(request.user, 'reporte-analitico', 'listar')
        unidad, _, _, _, _ = contexto(alcance, request.query_params)
        datos = resumen(alcance, request.query_params)
        auditar_analitica(request, unidad, 'REPORTAR', datos['contexto'])
        return Response(datos)


class AnaliticaExportar(Base):
    def post(self, request):
        validar_entrada(request.data, {'filtros', 'formato'})
        return self.exportar(request, request.data.get('filtros'), request.data.get('formato'))

    def exportar(self, request, filtros, formato):
        from html import escape
        from .analitica import contexto, resumen
        alcance = autorizar(request.user, 'reporte-analitico', 'listar')
        autorizar(request.user, 'reporte-ejecucion', 'descargar')
        if formato not in ('CSV', 'PDF') or not isinstance(filtros, dict):
            raise ValidationError('Formato o filtros inválidos.')
        unidad, _, _, _, _ = contexto(alcance, filtros)
        datos = resumen(alcance, filtros)
        filas = [['Nota', 'Matrícula actual', datos['metadatos']['matricula_actual']['advertencia']]]
        filas.extend(['Contexto', clave, valor] for clave, valor in datos['contexto'].items())
        filas.extend(['Indicador', clave, valor] for clave, valor in datos['indicadores'].items())
        for clave, serie in datos['series'].items():
            if serie is None:
                filas.append([clave, 'Serie no disponible', 'No fue posible calcular esta serie.'])
            else:
                filas.extend([clave, item['etiqueta'], item['valor']] for item in serie)
        ejecucion = EjecucionReporte(colegio=unidad.colegio, unidad_educativa=unidad, solicitante=request.user,
            actor_snapshot={'usuario_id': request.user.pk}, tipo='ANALITICO', fuente_codigo='ANALITICA',
            formato=formato, parametros_sanitizados=datos['contexto'], correlacion=uuid.uuid4())
        guardar(ejecucion)
        try:
            if formato == 'CSV':
                contenido, mime, extension = exportar_csv(['Sección', 'Concepto', 'Valor'], filas)
            else:
                seguras = [[escape(str(valor)) if valor is not None else '' for valor in fila] for fila in filas]
                contenido, mime, extension = exportar_pdf('Reporte analítico', ['Sección', 'Concepto', 'Valor'], seguras)
            if len(contenido) > Exportar.limite_bytes:
                raise ValueError('TAMANO_EXPORTACION')
            ejecucion.archivo_referencia = guardar_archivo(contenido, extension)
            ejecucion.archivo_mime = mime
            ejecucion.archivo_tamano = len(contenido)
            ejecucion.archivo_checksum = sha256(contenido).hexdigest()
            ejecucion.filas_resultado = len(filas)
            ejecucion.estado = 'COMPLETADO'
            ejecucion.finalizada_at = timezone.now()
            with transaction.atomic():
                guardar(ejecucion)
                auditar_analitica(request, unidad, 'EXPORTAR', datos['contexto'], formato, ejecucion)
        except Exception:
            if ejecucion.archivo_referencia:
                eliminar_archivo(ejecucion.archivo_referencia)
            ejecucion.archivo_referencia = None
            ejecucion.estado = 'ERROR'
            ejecucion.error_sanitizado = 'ERROR_ANALITICA_EXPORTACION'
            ejecucion.finalizada_at = timezone.now()
            guardar(ejecucion)
            auditar_analitica(request, unidad, 'EXPORTAR', datos['contexto'], formato, ejecucion)
            return Response({'detail': 'No se pudo exportar el reporte.'}, status=400)
        respuesta = HttpResponse(contenido, content_type=mime)
        respuesta['Content-Disposition'] = f'attachment; filename="reporte-analitico.{extension}"'
        respuesta['X-Reporte-Ejecucion'] = str(ejecucion.pk)
        return respuesta


_SAL_VOZ = 'reportes.voz.interpretacion.v1'
_INTENCIONES_VOZ = {'MATRICULA_ACTUAL', 'RENDIMIENTO', 'ASISTENCIA', 'INCIDENTES', 'ESTUDIANTES_INSCRITOS'}


def auditar_voz(request, alcance, accion, datos=None, unidad=None, ejecucion=None):
    datos = datos or {}
    campos = [f'{k}:{v}' for k, v in datos.items() if k in ('intencion', 'formato', 'estado', 'colegio', 'unidad_educativa', 'calendario_academico', 'periodo', 'curso', 'materia') and v is not None]
    registrar_evento(
        accion=accion, entidad='REPORTE_EJECUCION', entidad_id=ejecucion, request=request,
        colegio=unidad.colegio if unidad else Colegio.objects.filter(pk=alcance['colegio_id']).first(),
        unidad=unidad, inferir_unidad=False, cambios={'fuente': 'VOZ', 'campos': campos}, correlacion=uuid.uuid4())


class VozInterpretar(Base):
    def post(self, request):
        from .analitica import contexto
        from .voz import SolicitudVozInvalida, interpretar_texto, resolver_entidades
        from aplicaciones.calendario.models import Periodo
        alcance = autorizar(request.user, 'reporte-analitico', 'listar')
        validar_entrada(request.data, {'texto', 'contexto'})
        try:
            interpretacion = interpretar_texto(request.data.get('texto'))
        except SolicitudVozInvalida as exc:
            raise ValidationError({'texto': str(exc)}) from exc
        filtros = request.data.get('contexto') or {}
        if not isinstance(filtros, dict):
            raise ValidationError('Contexto inválido.')
        if interpretacion['estado'] == 'NO_SOPORTADO':
            auditar_voz(request, alcance, 'VOZ_RECHAZAR', {'estado': 'NO_SOPORTADO'})
            return Response({'estado': 'NO_SOPORTADO'})
        if interpretacion['reporte'] == 'ESTUDIANTES_INSCRITOS':
            autorizar(request.user, 'reporte-ejecucion', 'ejecutar')
        if interpretacion['formato'] in ('CSV', 'PDF'):
            autorizar(request.user, 'reporte-ejecucion', 'descargar')
        filtros = {k: v for k, v in filtros.items() if v not in (None, '')}
        faltantes = [k for k in ('unidad_educativa', 'calendario_academico') if not filtros.get(k)]
        if faltantes:
            return Response({'estado': 'FALTAN_DATOS', 'faltantes': faltantes})
        unidad, calendario, periodo, curso, materia = contexto(alcance, filtros)
        curso, materia, error_entidades = resolver_entidades(unidad, curso, materia, interpretacion.get('entidades', []))
        if error_entidades:
            return Response(error_entidades)
        if materia:
            from aplicaciones.academico.models import MateriaCurso
            if not MateriaCurso.objects.filter(curso=curso, materia_id=materia, estado='ACTIVO', eliminado_at__isnull=True, materia__estado='ACTIVO', materia__eliminado_at__isnull=True).exists():
                raise ValidationError({'materia': 'Materia no disponible.'})
        ordinal = interpretacion.get('periodo_ordinal')
        if ordinal:
            terminos = {1: ('primer', 'primero', '1er', '1ro'), 2: ('segundo', '2do', '2'), 3: ('tercer', 'tercero', '3er', '3ro')}[ordinal]
            from .voz import normalizar_texto
            opciones = [p for p in Periodo.objects.filter(calendario=calendario, tipo_division='TRI') if normalizar_texto(p.nombre).startswith(terminos)]
            if periodo and periodo not in opciones:
                raise ValidationError({'periodo': 'El periodo seleccionado no coincide con la solicitud.'})
            if not periodo and len(opciones) != 1:
                return Response({'estado': 'AMBIGUO' if opciones else 'FALTAN_DATOS', 'faltantes': ['periodo'], 'opciones': [{'id': p.pk, 'nombre': p.nombre} for p in opciones]})
            periodo = periodo or opciones[0]
            filtros['periodo'] = periodo.pk
        filtros = {'unidad_educativa': unidad.pk, 'calendario_academico': calendario.pk, 'periodo': periodo.pk if periodo else None, 'curso': curso.pk if curso else None, 'materia': materia}
        datos = {'usuario': request.user.pk, 'colegio': alcance['colegio_id'], 'intencion': interpretacion['reporte'], 'formato': interpretacion['formato'], 'filtros': filtros}
        token = signing.dumps(datos, salt=_SAL_VOZ, compress=True)
        auditar_voz(request, alcance, 'VOZ_INTERPRETAR', {**filtros, 'intencion': datos['intencion'], 'formato': datos['formato'], 'estado': 'LISTO'}, unidad)
        return Response({'estado': 'LISTO', 'intencion': datos['intencion'], 'formato': datos['formato'], 'filtros': filtros, 'colegio': alcance['colegio_id'], 'token_interpretacion': token,
            'advertencias': ['La matrícula representa la situación actual, no histórica.'] if datos['intencion'] == 'MATRICULA_ACTUAL' else []})


class VozEjecutar(Base):
    def post(self, request):
        from .analitica import contexto, resumen
        from .fuentes_operativas import ejecutar_fuente
        alcance = autorizar(request.user, 'reporte-analitico', 'listar')
        validar_entrada(request.data, {'token_interpretacion', 'confirmacion'})
        if request.data.get('confirmacion') is not True:
            raise ValidationError('Se requiere confirmación explícita.')
        try:
            datos = signing.loads(request.data.get('token_interpretacion', ''), salt=_SAL_VOZ, max_age=300)
        except (signing.BadSignature, TypeError):
            auditar_voz(request, alcance, 'VOZ_RECHAZAR', {'estado': 'TOKEN_INVALIDO'})
            raise ValidationError('Interpretación inválida o vencida.')
        if not isinstance(datos, dict) or datos.get('usuario') != request.user.pk or datos.get('colegio') != alcance['colegio_id'] or datos.get('intencion') not in _INTENCIONES_VOZ or datos.get('formato') not in ('VISTA', 'CSV', 'PDF') or not isinstance(datos.get('filtros'), dict):
            auditar_voz(request, alcance, 'VOZ_RECHAZAR', {'estado': 'TOKEN_INVALIDO'})
            raise ValidationError('Interpretación inválida o vencida.')
        filtros = datos['filtros']
        unidad, _, _, curso, materia = contexto(alcance, filtros)
        if materia:
            from aplicaciones.academico.models import MateriaCurso
            if not MateriaCurso.objects.filter(curso=curso, materia_id=materia, estado='ACTIVO', eliminado_at__isnull=True, materia__estado='ACTIVO', materia__eliminado_at__isnull=True).exists():
                raise ValidationError({'materia': 'Materia no disponible.'})
        if datos['intencion'] == 'ESTUDIANTES_INSCRITOS':
            especificacion = {
                'columnas': ['nombre', 'curso'],
                'filtros': [{'campo': 'unidad', 'operador': 'eq', 'valor': unidad.pk}],
                'orden': [{'campo': 'curso', 'direccion': 'asc'}],
            }
            if curso:
                especificacion['filtros'].append({'campo': 'curso', 'operador': 'eq', 'valor': curso.pk})
            _, filas, hay_mas = ejecutar_fuente(
                request.user, 'ESTUDIANTES_INSCRITOS', especificacion, limite=100, unidad_id=unidad.pk)
            respuesta = Response({
                'tipo': 'ESTUDIANTES_INSCRITOS',
                'columnas': ['Estudiante', 'Curso'],
                'filas': filas,
                'limite': 100,
                'hay_mas': hay_mas,
            })
        elif datos['formato'] == 'VISTA':
            respuesta = Response(resumen(alcance, filtros))
        else:
            respuesta = AnaliticaExportar().exportar(request, filtros, datos['formato'])
        auditar_voz(request, alcance, 'VOZ_EJECUTAR', {**filtros, 'intencion': datos['intencion'], 'formato': datos['formato'], 'estado': 'COMPLETADO' if respuesta.status_code == 200 else 'ERROR'}, unidad, respuesta.get('X-Reporte-Ejecucion'))
        return respuesta

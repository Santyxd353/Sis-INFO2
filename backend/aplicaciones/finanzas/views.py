from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication

from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.usuarios.auditoria import registrar_evento
from aplicaciones.usuarios.feature_access import SchoolPagination, id_filters, scoped
from aplicaciones.usuarios.tenancy import es_superadmin, validar_unidad

from . import avisos, servicios
from .fechas import hoy
from .models import AsignacionBeca, Beca, ObligacionPago, Pago, PlanPago
from .recibos import generar_recibo_pdf
from .serializers import (
    AnularObligacionSerializer, AsignacionBecaSerializer, AsignarPlanSerializer, BecaSerializer,
    EstudianteElegibleSerializer, GenerarCuotasSerializer, ObligacionPagoSerializer, PagoSerializer,
    ParametrosSimulacionSerializer, PlanPagoSerializer, RegistrarPagoSerializer, RevocarBecaSerializer,
)

ACCION_POR_METODO = {
    'GET': 'listar', 'HEAD': 'listar', 'OPTIONS': 'listar',
    'POST': 'crear', 'PUT': 'editar', 'PATCH': 'editar',
}


class PermisoFinanzas(BasePermission):
    """Administrativos según permisos del puesto; familias solo leen lo suyo."""

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        if es_superadmin(user):
            return request.method in SAFE_METHODS
        accion = view.acciones_personalizadas.get(getattr(view, 'action', None)) or ACCION_POR_METODO.get(request.method)
        if accion is None:
            return False
        from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
        from aplicaciones.usuarios.privilegios import puede
        autorizar_acceso_modelo(user, view.modelo_permiso)
        if hasattr(user, 'admin'):
            return puede(user, view.modelo_permiso, accion)
        permitida = request.method in SAFE_METHODS or (
            getattr(view, 'action', None) in getattr(view, 'acciones_familiares', ())
        )
        return view.lectura_familiar and permitida and (hasattr(user, 'tutor') or hasattr(user, 'estudiante'))


def en_alcance(user, queryset, campo_unidad, campo_estudiante='estudiante'):
    """Administrativos: sus unidades. Tutor: sus representados. Estudiante: lo propio."""
    if es_superadmin(user) or hasattr(user, 'admin'):
        return scoped(queryset, user, campo_unidad)
    prefijo = f'{campo_estudiante}__' if campo_estudiante else ''
    if hasattr(user, 'tutor'):
        return queryset.filter(**{f'{prefijo}tutores__tutor__usuario': user}).distinct()
    if hasattr(user, 'estudiante'):
        return queryset.filter(**{f'{prefijo}pk': user.estudiante.pk})
    return queryset.none()


def obligaciones_base():
    return ObligacionPago.objects.select_related(
        'estudiante__usuario', 'estudiante__curso', 'cuota__plan__calendario_academico', 'asignacion_beca__beca',
    )


def pagos_base():
    return Pago.objects.select_related(
        'estudiante__usuario', 'estudiante__curso', 'registrado_por', 'unidad_educativa__colegio',
    ).prefetch_related('detalles__obligacion__cuota__plan')


def _auditar(request, accion, entidad, objeto, unidad, **cambios):
    registrar_evento(
        accion=accion, entidad=entidad, request=request, entidad_id=str(objeto.pk),
        unidad=unidad, cambios=cambios or None,
    )


def _filtrar_texto(queryset, params, campo, parametro='nombre'):
    valor = (params.get(parametro) or '').strip()
    return queryset.filter(**{f'{campo}__icontains': valor}) if valor else queryset


def _filtrar_opcion(queryset, params, parametro, campo, opciones):
    valor = params.get(parametro)
    if valor in (None, ''):
        return queryset
    if valor not in opciones:
        raise serializers.ValidationError({parametro: 'Valor no válido.'})
    return queryset.filter(**{campo: valor})


class BaseFinanzasViewSet(ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoFinanzas]
    pagination_class = SchoolPagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    acciones_personalizadas = {}
    lectura_familiar = False


class PlanPagoViewSet(BaseFinanzasViewSet):
    """HU-22: planes de pago por gestión con generación de cuotas y asignación."""

    serializer_class = PlanPagoSerializer
    modelo_permiso = 'plan-pago'
    acciones_personalizadas = {
        'generar_cuotas': 'editar', 'activar': 'editar', 'desactivar': 'desactivar', 'asignar': 'asignar',
    }

    def get_queryset(self):
        queryset = PlanPago.objects.select_related(
            'unidad_educativa', 'calendario_academico',
        ).prefetch_related('cuotas').annotate(
            num_estudiantes=Count('cuotas__obligaciones__estudiante', distinct=True),
        )
        queryset = scoped(queryset, self.request.user, 'unidad_educativa_id')
        params = self.request.query_params
        queryset = id_filters(queryset, params, {
            'unidad_educativa': 'unidad_educativa_id', 'calendario_academico': 'calendario_academico_id',
        })
        queryset = _filtrar_opcion(queryset, params, 'estado', 'estado', PlanPago.Estado.values)
        queryset = _filtrar_opcion(queryset, params, 'nivel_educativo', 'nivel_educativo', ('INI', 'PRI', 'SEC'))
        return _filtrar_texto(queryset, params, 'nombre').order_by('-calendario_academico__año', 'nombre')

    def _respuesta(self, plan, codigo=status.HTTP_200_OK):
        return Response(self.get_serializer(self.get_queryset().get(pk=plan.pk)).data, status=codigo)

    def perform_create(self, serializer):
        validar_unidad(self.request.user, serializer.validated_data['unidad_educativa'])
        with transaction.atomic():
            plan = serializer.save(created_by=self.request.user)
            _auditar(self.request, 'CREAR', 'PLAN_PAGO', plan, plan.unidad_educativa, estado_nuevo=plan.estado)

    def perform_update(self, serializer):
        validar_unidad(self.request.user, serializer.instance.unidad_educativa)
        if 'unidad_educativa' in serializer.validated_data:
            validar_unidad(self.request.user, serializer.validated_data['unidad_educativa'])
        with transaction.atomic():
            plan = serializer.save()
            _auditar(self.request, 'ACTUALIZAR', 'PLAN_PAGO', plan, plan.unidad_educativa,
                     campos=list(serializer.validated_data))

    @action(detail=True, methods=['post'], url_path='generar-cuotas')
    def generar_cuotas(self, request, pk=None):
        plan = self.get_object()
        validar_unidad(request.user, plan.unidad_educativa)
        datos = GenerarCuotasSerializer(data=request.data, context={'plan': plan})
        datos.is_valid(raise_exception=True)
        with transaction.atomic():
            cuotas = servicios.generar_cuotas(plan, datos.validated_data['fecha_primer_vencimiento'])
            _auditar(request, 'ACTUALIZAR', 'PLAN_PAGO', plan, plan.unidad_educativa,
                     campos=['cuotas'], cantidad_filas=len(cuotas))
        return self._respuesta(plan)

    @action(detail=True, methods=['post'])
    def activar(self, request, pk=None):
        plan = self.get_object()
        validar_unidad(request.user, plan.unidad_educativa)
        with transaction.atomic():
            servicios.activar_plan(plan)
            _auditar(request, 'ACTUALIZAR', 'PLAN_PAGO', plan, plan.unidad_educativa,
                     estado_anterior='BORRADOR', estado_nuevo='ACTIVO')
        return self._respuesta(plan)

    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        plan = self.get_object()
        validar_unidad(request.user, plan.unidad_educativa)
        if plan.estado == PlanPago.Estado.INACTIVO:
            raise serializers.ValidationError({'detail': 'El plan ya está inactivo.'})
        anterior = plan.estado
        with transaction.atomic():
            plan.estado = PlanPago.Estado.INACTIVO
            plan.save(update_fields=['estado', 'updated_at'])
            _auditar(request, 'DESACTIVAR', 'PLAN_PAGO', plan, plan.unidad_educativa,
                     estado_anterior=anterior, estado_nuevo='INACTIVO')
        return self._respuesta(plan)

    @action(detail=True, methods=['post'])
    def asignar(self, request, pk=None):
        plan = self.get_object()
        validar_unidad(request.user, plan.unidad_educativa)
        datos = AsignarPlanSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        ids = datos.validated_data.get('estudiantes')
        estudiantes = servicios.estudiantes_por_ids_o_curso(plan, ids, datos.validated_data.get('curso'))
        inexistentes = sorted(set(ids or []) - {e.pk for e in estudiantes})
        with transaction.atomic():
            resultado = servicios.asignar_plan(plan, estudiantes)
            _auditar(request, 'ACTUALIZAR', 'PLAN_PAGO', plan, plan.unidad_educativa,
                     resultado='asignacion', cantidad_filas=resultado['obligaciones_creadas'])
        resultado['rechazados'] += [{'estudiante': pk_, 'motivo': 'El estudiante no existe.'} for pk_ in inexistentes]
        return Response(resultado)


class BecaViewSet(BaseFinanzasViewSet):
    """HU-23: catálogo de becas y descuentos de la unidad educativa."""

    serializer_class = BecaSerializer
    modelo_permiso = 'beca'
    acciones_personalizadas = {'desactivar': 'desactivar', 'activar': 'editar'}

    def get_queryset(self):
        queryset = Beca.objects.select_related('unidad_educativa').annotate(
            num_vigentes=Count('asignaciones', filter=Q(asignaciones__estado=AsignacionBeca.Estado.VIGENTE)),
        )
        queryset = scoped(queryset, self.request.user, 'unidad_educativa_id')
        params = self.request.query_params
        queryset = id_filters(queryset, params, {'unidad_educativa': 'unidad_educativa_id'})
        queryset = _filtrar_opcion(queryset, params, 'estado', 'estado', Beca.Estado.values)
        queryset = _filtrar_opcion(queryset, params, 'tipo_descuento', 'tipo_descuento', Beca.TipoDescuento.values)
        return _filtrar_texto(queryset, params, 'nombre').order_by('nombre')

    def perform_create(self, serializer):
        validar_unidad(self.request.user, serializer.validated_data['unidad_educativa'])
        with transaction.atomic():
            beca = serializer.save()
            _auditar(self.request, 'CREAR', 'BECA', beca, beca.unidad_educativa)

    def perform_update(self, serializer):
        validar_unidad(self.request.user, serializer.instance.unidad_educativa)
        if serializer.instance.asignaciones.filter(estado=AsignacionBeca.Estado.VIGENTE).exists() and (
            {'tipo_descuento', 'valor'} & set(serializer.validated_data)
        ):
            raise serializers.ValidationError(
                {'detail': 'No se puede cambiar el descuento de una beca con asignaciones vigentes.'},
            )
        with transaction.atomic():
            beca = serializer.save()
            _auditar(self.request, 'ACTUALIZAR', 'BECA', beca, beca.unidad_educativa,
                     campos=list(serializer.validated_data))

    def _cambiar_estado(self, request, nuevo, accion_auditoria):
        beca = self.get_object()
        validar_unidad(request.user, beca.unidad_educativa)
        if beca.estado == nuevo:
            raise serializers.ValidationError({'detail': f'La beca ya está en estado {nuevo.lower()}.'})
        anterior = beca.estado
        with transaction.atomic():
            beca.estado = nuevo
            beca.save(update_fields=['estado', 'updated_at'])
            _auditar(request, accion_auditoria, 'BECA', beca, beca.unidad_educativa,
                     estado_anterior=anterior, estado_nuevo=nuevo)
        return Response(self.get_serializer(self.get_queryset().get(pk=beca.pk)).data)

    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        return self._cambiar_estado(request, Beca.Estado.INACTIVO, 'DESACTIVAR')

    @action(detail=True, methods=['post'])
    def activar(self, request, pk=None):
        return self._cambiar_estado(request, Beca.Estado.ACTIVO, 'ACTUALIZAR')


class AsignacionBecaViewSet(BaseFinanzasViewSet):
    """HU-23: otorgamiento y revocación de becas a estudiantes."""

    serializer_class = AsignacionBecaSerializer
    modelo_permiso = 'beca'
    acciones_personalizadas = {'create': 'asignar', 'revocar': 'asignar'}
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        queryset = AsignacionBeca.objects.select_related(
            'beca', 'estudiante__usuario', 'estudiante__curso', 'calendario_academico', 'asignado_por',
        )
        queryset = scoped(queryset, self.request.user, 'beca__unidad_educativa_id')
        params = self.request.query_params
        queryset = id_filters(queryset, params, {
            'unidad_educativa': 'beca__unidad_educativa_id', 'beca': 'beca_id',
            'estudiante': 'estudiante_id', 'calendario_academico': 'calendario_academico_id',
        })
        queryset = _filtrar_opcion(queryset, params, 'estado', 'estado', AsignacionBeca.Estado.values)
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        beca = serializer.validated_data['beca']
        validar_unidad(self.request.user, beca.unidad_educativa)
        with transaction.atomic():
            asignacion = serializer.save(asignado_por=self.request.user)
            actualizadas = servicios.recalcular_pendientes(
                asignacion.estudiante_id, asignacion.calendario_academico_id,
            )
            _auditar(self.request, 'CREAR', 'ASIGNACION_BECA', asignacion, beca.unidad_educativa,
                     estado_nuevo='VIGENTE', cantidad_filas=actualizadas)
            avisos.avisar_beca(asignacion)

    @action(detail=True, methods=['post'])
    def revocar(self, request, pk=None):
        asignacion = self.get_object()
        validar_unidad(request.user, asignacion.beca.unidad_educativa)
        if asignacion.estado != AsignacionBeca.Estado.VIGENTE:
            raise serializers.ValidationError({'detail': 'La beca ya fue revocada.'})
        datos = RevocarBecaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        with transaction.atomic():
            asignacion.estado = AsignacionBeca.Estado.REVOCADA
            asignacion.revocado_at = timezone.now()
            asignacion.motivo_revocacion = datos.validated_data['motivo']
            asignacion.save(update_fields=['estado', 'revocado_at', 'motivo_revocacion'])
            actualizadas = servicios.recalcular_pendientes(
                asignacion.estudiante_id, asignacion.calendario_academico_id,
            )
            _auditar(request, 'DESACTIVAR', 'ASIGNACION_BECA', asignacion, asignacion.beca.unidad_educativa,
                     estado_anterior='VIGENTE', estado_nuevo='REVOCADA', cantidad_filas=actualizadas)
            avisos.avisar_beca(asignacion, revocada=True)
        return Response(self.get_serializer(asignacion).data)

    @action(detail=False, methods=['get'])
    def estudiantes(self, request):
        queryset = scoped(
            Estudiante.objects.select_related('usuario', 'curso').filter(estado=True),
            request.user, 'unidad_id',
        )
        queryset = id_filters(queryset, request.query_params, {'unidad_educativa': 'unidad_id', 'curso': 'curso_id'})
        buscar = (request.query_params.get('buscar') or '').strip()
        if buscar:
            queryset = queryset.filter(
                Q(usuario__nombre__icontains=buscar) | Q(usuario__apellido__icontains=buscar)
                | Q(rude__icontains=buscar),
            )
        return Response(EstudianteElegibleSerializer(queryset[:50], many=True).data)


class ObligacionPagoViewSet(ReadOnlyModelViewSet):
    """Obligaciones generadas por los planes; las familias consultan las propias."""

    serializer_class = ObligacionPagoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoFinanzas]
    pagination_class = SchoolPagination
    modelo_permiso = 'obligacion-pago'
    acciones_personalizadas = {'anular': 'editar'}
    lectura_familiar = True

    def get_queryset(self):
        queryset = en_alcance(self.request.user, obligaciones_base(), 'cuota__plan__unidad_educativa_id')
        params = self.request.query_params
        queryset = id_filters(queryset, params, {
            'estudiante': 'estudiante_id', 'plan': 'cuota__plan_id', 'curso': 'estudiante__curso_id',
            'calendario_academico': 'cuota__plan__calendario_academico_id',
            'unidad_educativa': 'cuota__plan__unidad_educativa_id',
        })
        queryset = _filtrar_opcion(queryset, params, 'estado', 'estado', ObligacionPago.Estado.values)
        if params.get('vencidas') in ('1', 'true'):
            queryset = queryset.filter(
                estado=ObligacionPago.Estado.PENDIENTE, fecha_vencimiento__lt=hoy(),
            )
        return queryset.order_by('fecha_vencimiento', 'estudiante__usuario__apellido', 'cuota__numero')

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        obligacion = self.get_object()
        unidad = obligacion.cuota.plan.unidad_educativa
        validar_unidad(request.user, unidad)
        if obligacion.estado != ObligacionPago.Estado.PENDIENTE:
            raise serializers.ValidationError({'detail': 'Solo se pueden anular obligaciones pendientes.'})
        if obligacion.monto_pagado > 0:
            raise serializers.ValidationError({'detail': 'La cuota tiene pagos registrados; anule primero esos pagos.'})
        datos = AnularObligacionSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        with transaction.atomic():
            obligacion.estado = ObligacionPago.Estado.ANULADA
            obligacion.motivo_anulacion = datos.validated_data['motivo']
            obligacion.save(update_fields=['estado', 'motivo_anulacion', 'updated_at'])
            _auditar(request, 'DESACTIVAR', 'OBLIGACION_PAGO', obligacion, unidad,
                     estado_anterior='PENDIENTE', estado_nuevo='ANULADA')
        return Response(self.get_serializer(obligacion).data)


class PagoViewSet(ReadOnlyModelViewSet):
    """HU-24: registro de pagos con recibo; las familias consultan los propios."""

    serializer_class = PagoSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoFinanzas]
    pagination_class = SchoolPagination
    modelo_permiso = 'pago'
    acciones_personalizadas = {'create': 'crear', 'anular': 'anular'}
    lectura_familiar = True

    def get_queryset(self):
        queryset = en_alcance(self.request.user, pagos_base(), 'unidad_educativa_id')
        params = self.request.query_params
        queryset = id_filters(queryset, params, {
            'estudiante': 'estudiante_id', 'unidad_educativa': 'unidad_educativa_id',
            'curso': 'estudiante__curso_id', 'numero_recibo': 'numero_recibo',
        })
        queryset = _filtrar_opcion(queryset, params, 'estado', 'estado', Pago.Estado.values)
        queryset = _filtrar_opcion(queryset, params, 'metodo', 'metodo', Pago.Metodo.values)
        for parametro, campo in (('desde', 'fecha_pago__gte'), ('hasta', 'fecha_pago__lte')):
            valor = params.get(parametro)
            if valor:
                queryset = queryset.filter(**{campo: serializers.DateField().run_validation(valor)})
        return queryset.order_by('-fecha_pago', '-numero_recibo')

    def create(self, request):
        datos = RegistrarPagoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        valores = datos.validated_data
        estudiante = get_object_or_404(
            scoped(Estudiante.objects.select_related('unidad'), request.user, 'unidad_id'), pk=valores['estudiante'],
        )
        validar_unidad(request.user, estudiante.unidad)
        with transaction.atomic():
            pago = servicios.registrar_pago(
                usuario=request.user, estudiante=estudiante, monto=valores['monto'], metodo=valores['metodo'],
                fecha_pago=valores.get('fecha_pago') or hoy(), referencia=valores['referencia'].strip(),
                observaciones=valores['observaciones'].strip(), obligacion_ids=valores.get('obligaciones'),
            )
            _auditar(request, 'CREAR', 'PAGO_PENSION', pago, pago.unidad_educativa,
                     metodo=pago.metodo, cantidad_filas=pago.detalles.count())
        return Response(self.get_serializer(pagos_base().get(pk=pago.pk)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        pago = self.get_object()
        validar_unidad(request.user, pago.unidad_educativa)
        datos = RevocarBecaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        with transaction.atomic():
            servicios.anular_pago(pago, request.user, datos.validated_data['motivo'])
            _auditar(request, 'DESACTIVAR', 'PAGO_PENSION', pago, pago.unidad_educativa,
                     estado_anterior='VALIDO', estado_nuevo='ANULADO')
        return Response(self.get_serializer(pagos_base().get(pk=pago.pk)).data)

    @action(detail=True, methods=['get'])
    def recibo(self, request, pk=None):
        pago = self.get_object()
        respuesta = HttpResponse(generar_recibo_pdf(pago), content_type='application/pdf')
        respuesta['Content-Disposition'] = f'inline; filename="recibo-{pago.numero_recibo:06d}.pdf"'
        return respuesta


class BaseConsultaFinanzas(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [PermisoFinanzas]
    acciones_personalizadas = {}
    lectura_familiar = False

    def obligaciones(self, request):
        queryset = en_alcance(request.user, obligaciones_base(), 'cuota__plan__unidad_educativa_id')
        return id_filters(queryset, request.query_params, {
            'unidad_educativa': 'cuota__plan__unidad_educativa_id', 'curso': 'estudiante__curso_id',
            'calendario_academico': 'cuota__plan__calendario_academico_id',
        })


class EstadoCuentaView(BaseConsultaFinanzas):
    """HU-24: estado de cuenta de un estudiante, también visible para su familia."""

    modelo_permiso = 'estado-cuenta'
    lectura_familiar = True

    def get(self, request):
        estudiantes = en_alcance(request.user, Estudiante.objects.select_related('usuario', 'curso'), 'unidad_id', None)
        estudiante_id = request.query_params.get('estudiante')
        if not estudiante_id and hasattr(request.user, 'estudiante'):
            estudiante_id = request.user.estudiante.pk
        if not estudiante_id:
            raise serializers.ValidationError({'estudiante': 'Indique el estudiante.'})
        estudiante = get_object_or_404(estudiantes, pk=serializers.IntegerField(min_value=1).run_validation(estudiante_id))
        obligaciones = self.obligaciones(request).filter(estudiante=estudiante).order_by('fecha_vencimiento', 'cuota__numero')
        pagos = pagos_base().filter(estudiante=estudiante).order_by('-fecha_pago', '-numero_recibo')
        calendario = request.query_params.get('calendario_academico')
        if calendario:
            pagos = pagos.filter(detalles__obligacion__cuota__plan__calendario_academico_id=calendario).distinct()
        datos = servicios.estado_cuenta(estudiante, obligaciones, pagos)
        datos.update({
            'estudiante_nombre': f'{estudiante.usuario.nombre} {estudiante.usuario.apellido}'.strip(),
            'rude': estudiante.rude, 'curso_nombre': estudiante.curso.nombre if estudiante.curso else None,
            'obligaciones': ObligacionPagoSerializer(datos['obligaciones'], many=True).data,
            'pagos': PagoSerializer(datos['pagos'], many=True).data,
        })
        return Response(datos)


class MorosidadView(BaseConsultaFinanzas):
    """HU-26: reporte de morosidad por estudiante y por antigüedad de la deuda."""

    modelo_permiso = 'morosidad'

    def get(self, request):
        dias = serializers.IntegerField(min_value=1, max_value=365).run_validation(
            request.query_params.get('dias_minimos') or 1,
        )
        return Response(servicios.morosidad(self.obligaciones(request), dias))


class SimulacionTributariaView(BaseConsultaFinanzas):
    """HU-26: simulación de IVA e IT sobre los ingresos por pensiones."""

    modelo_permiso = 'simulacion-tributaria'

    def get(self, request):
        parametros = ParametrosSimulacionSerializer(data=request.query_params)
        parametros.is_valid(raise_exception=True)
        valores = parametros.validated_data
        pagos = id_filters(
            scoped(Pago.objects.all(), request.user, 'unidad_educativa_id'), request.query_params,
            {'unidad_educativa': 'unidad_educativa_id'},
        )
        return Response(servicios.simulacion_tributaria(
            pagos, self.obligaciones(request), valores['desde'], valores['hasta'],
            valores['tasa_iva'], valores['tasa_it'], valores['credito_fiscal'],
        ))

from datetime import timedelta
from hmac import compare_digest
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from django.conf import settings

from aplicaciones.institucion.models import Colegio
from aplicaciones.usuarios.auditoria import registrar_evento
from aplicaciones.usuarios.permissions import IsSuperAdmin, PermisoPorPuesto
from aplicaciones.usuarios.tenancy import es_superadmin, resolver_alcance
from aplicaciones.usuarios.utils import get_client_ip, registrar_bitacora

from . import qr_simulado, servicios, stripe_checkout, vendis
from .models import MetodoPago, MetodoPagoColegio, Pago, Plan, Suscripcion
from .serializers import (
    ContratarSuscripcionSerializer,
    PagoSerializer,
    MetodoPagoSerializer, MetodoPagoColegioSerializer,
    PlanSerializer,
    SuscripcionSerializer,
    datos_estado_suscripcion,
    proximo_vencimiento_contratacion,
)


class PlanesPublicosView(ListAPIView):
    """Catálogo comercial disponible sin iniciar sesión."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    serializer_class = PlanSerializer
    queryset = Plan.objects.filter(
        estado=Plan.Estado.ACTIVO, eliminado_at__isnull=True,
    ).order_by('precio', 'nombre')


class MetodosPagoPublicosView(ListAPIView):
    """Métodos que pueden elegirse durante el alta institucional pública."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    serializer_class = MetodoPagoSerializer
    queryset = MetodoPago.objects.filter(activo=True).order_by('nombre')

    def get_queryset(self):
        metodos = super().get_queryset()
        if not stripe_checkout.configurado():
            metodos = metodos.exclude(codigo=MetodoPago.Codigo.STRIPE)
        if not vendis.configurado():
            metodos = metodos.exclude(codigo=MetodoPago.Codigo.PASARELA)
        if not settings.QR_DEMO_PLAN_IDS:
            metodos = metodos.exclude(codigo=MetodoPago.Codigo.QR_SIMULADO)
        return metodos


class SuperadminOPuesto(BasePermission):
    """Superadministrador o puesto con permiso sobre el modelo."""

    def has_permission(self, request, view):
        if IsSuperAdmin().has_permission(request, view):
            return True
        return PermisoPorPuesto().has_permission(request, view)


class PuedeConsultarFacturacion(BasePermission):
    def has_permission(self, request, view):
        from aplicaciones.usuarios.privilegios import puede
        return es_superadmin(request.user) or puede(request.user, view.basename, 'listar')


class PuedeConfigurarMetodoColegio(BasePermission):
    def has_permission(self, request, view):
        if es_superadmin(request.user):
            return True
        try:
            return resolver_alcance(request.user).get('tipo') == 'COLEGIO'
        except Exception:
            return False


def _auditar(request, *, accion, entidad, descripcion, entidad_id=None,
             colegio=None, cambios=None, accion_bitacora='crear'):
    if getattr(request.user, 'is_authenticated', False):
        registrar_bitacora(
            request.user, get_client_ip(request), entidad.lower(), accion_bitacora, descripcion,
        )
    registrar_evento(
        accion=accion, entidad=entidad, request=request, entidad_id=entidad_id,
        colegio=colegio, cambios=cambios,
    )


class PlanViewSet(viewsets.ModelViewSet):
    """Catálogo de planes SaaS. Solo el Superadministrador lo gestiona."""

    serializer_class = PlanSerializer
    queryset = Plan.objects.all().order_by('nombre')

    def get_queryset(self):
        qs = Plan.objects.filter(eliminado_at__isnull=True)
        estado = self.request.query_params.get('estado')
        if estado in Plan.Estado.values:
            qs = qs.filter(estado=estado)
        if not es_superadmin(self.request.user):
            qs = qs.filter(estado=Plan.Estado.ACTIVO)
        return qs

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        plan = serializer.save()
        _auditar(
            self.request, accion='CREAR', entidad='PLAN',
            descripcion=f'Creación del plan {plan.nombre}', entidad_id=plan.pk,
            cambios={'campos': list(serializer.validated_data.keys())},
        )


    def perform_update(self, serializer):
        plan = serializer.save()
        _auditar(
            self.request, accion='ACTUALIZAR', entidad='PLAN',
            descripcion=f'Actualizacion del plan {plan.nombre}', entidad_id=plan.pk,
            cambios={'campos': list(serializer.validated_data.keys())},
            accion_bitacora='editar',
        )

    def perform_destroy(self, instance):
        instance.desactivar()
        _auditar(
            self.request, accion='DESACTIVAR', entidad='PLAN',
            descripcion=f'Inactivacion del plan {instance.nombre}', entidad_id=instance.pk,
            accion_bitacora='editar',
        )


class MetodoPagoViewSet(viewsets.ModelViewSet):
    """Configuración global de canales de pago, exclusiva de Superadmin."""

    serializer_class = MetodoPagoSerializer
    queryset = MetodoPago.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def perform_create(self, serializer):
        metodo = serializer.save()
        _auditar(self.request, accion='CREAR', entidad='PAGO',
                 descripcion=f'Configuración del método de pago {metodo.nombre}',
                 entidad_id=metodo.pk, cambios={'campos': list(serializer.validated_data)})

    def perform_update(self, serializer):
        metodo = serializer.save()
        _auditar(self.request, accion='ACTUALIZAR', entidad='PAGO',
                 descripcion=f'Actualización del método de pago {metodo.nombre}',
                 entidad_id=metodo.pk, cambios={'campos': list(serializer.validated_data)})

    def perform_destroy(self, instance):
        instance.activo = False
        instance.save(update_fields=['activo', 'actualizado_at'])
        _auditar(self.request, accion='DESACTIVAR', entidad='PAGO',
                 descripcion=f'Desactivación del método de pago {instance.nombre}', entidad_id=instance.pk)

    def perform_update_plan_legacy(self, serializer):
        plan = serializer.save()
        _auditar(
            self.request, accion='ACTUALIZAR', entidad='PLAN',
            descripcion=f'Actualización del plan {plan.nombre}', entidad_id=plan.pk,
            cambios={'campos': list(serializer.validated_data.keys())},
            accion_bitacora='editar',
        )

    def perform_destroy_plan_legacy(self, instance):
        """Baja lógica: conserva el historial de suscripciones y pagos."""
        instance.desactivar()
        _auditar(
            self.request, accion='DESACTIVAR', entidad='PLAN',
            descripcion=f'Inactivación del plan {instance.nombre}', entidad_id=instance.pk,
            accion_bitacora='editar',
        )


class MetodoPagoColegioViewSet(viewsets.ModelViewSet):
    serializer_class = MetodoPagoColegioSerializer
    http_method_names = ['get', 'post', 'patch', 'put', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = MetodoPagoColegio.objects.select_related('colegio', 'metodo')
        if es_superadmin(self.request.user):
            colegio = self.request.query_params.get('colegio')
            return qs.filter(colegio_id=colegio) if colegio else qs
        colegio_id = servicios.colegio_del_usuario(self.request.user)
        return qs.filter(colegio_id=colegio_id, metodo__activo=True) if colegio_id else qs.none()

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), PuedeConfigurarMetodoColegio()]
        return [permissions.IsAuthenticated(), PuedeConfigurarMetodoColegio()]

    @action(detail=False, methods=['get'], url_path='disponibles')
    def disponibles(self, request):
        """Catálogo activo de la plataforma con la configuración del colegio."""
        ctx = resolver_alcance(request.user)
        colegio_id = request.query_params.get('colegio') if es_superadmin(request.user) else ctx.get('colegio_id')
        if not colegio_id:
            raise ValidationError({'colegio': 'No hay un colegio asociado.'})
        configuraciones = {
            item.metodo_id: item for item in MetodoPagoColegio.objects.filter(
                colegio_id=colegio_id, activo=True, metodo__activo=True,
            ).select_related('metodo', 'colegio')
        }
        resultado = []
        for metodo in MetodoPago.objects.filter(activo=True).order_by('nombre'):
            item = configuraciones.get(metodo.pk)
            resultado.append({
                'metodo': MetodoPagoSerializer(metodo).data,
                'configuracion_colegio': MetodoPagoColegioSerializer(item).data if item else None,
            })
        return Response(resultado)

    def perform_create(self, serializer):
        if es_superadmin(self.request.user):
            colegio_id = self.request.data.get('colegio')
            if not colegio_id:
                raise ValidationError({'colegio': 'Debe indicar el colegio.'})
            colegio = Colegio.objects.get(pk=colegio_id)
        else:
            colegio_id = servicios.colegio_del_usuario(self.request.user)
            if not colegio_id:
                raise PermissionDenied('El usuario no tiene colegio asociado.')
            colegio = Colegio.objects.get(pk=colegio_id)
        metodo = serializer.validated_data['metodo']
        if MetodoPagoColegio.objects.filter(colegio=colegio, metodo=metodo).exists():
            raise ValidationError({'metodo': 'El método ya está configurado para este colegio.'})
        registro = serializer.save(colegio=colegio)
        _auditar(self.request, accion='CREAR', entidad='PAGO', descripcion=f'Configuración de método {registro.metodo.codigo} para {colegio.nombre}', entidad_id=registro.pk, colegio=colegio, cambios={'campos': list(serializer.validated_data)})

    def perform_update(self, serializer):
        registro = serializer.save()
        _auditar(self.request, accion='ACTUALIZAR', entidad='PAGO', descripcion=f'Actualización de método {registro.metodo.codigo}', entidad_id=registro.pk, colegio=registro.colegio, cambios={'campos': list(serializer.validated_data)})

    def perform_destroy(self, instance):
        instance.activo = False
        instance.save(update_fields=['activo', 'actualizado_at'])
        _auditar(self.request, accion='DESACTIVAR', entidad='PAGO', descripcion=f'Desactivación de método {instance.metodo.codigo}', entidad_id=instance.pk, colegio=instance.colegio)


class SuscripcionViewSet(viewsets.ModelViewSet):
    """Suscripciones de los colegios (tenant = colegio).

    El Superadministrador gestiona todas; un colegio solo puede consultar las
    suyas y contratar planes (la suscripción nace PENDIENTE de pago).
    """

    serializer_class = SuscripcionSerializer
    queryset = Suscripcion.objects.select_related('colegio', 'plan')

    def get_queryset(self):
        qs = Suscripcion.objects.select_related('colegio', 'plan').order_by(
            '-fecha_inicio', '-id',
        )
        user = self.request.user
        if es_superadmin(user):
            colegio = self.request.query_params.get('colegio')
            if colegio:
                qs = qs.filter(colegio_id=colegio)
            estado = self.request.query_params.get('estado')
            if estado in Suscripcion.Estado.values:
                qs = qs.filter(estado=estado)
            return qs
        colegio_id = servicios.colegio_del_usuario(user)
        if colegio_id is None:
            return qs.none()
        return qs.filter(colegio_id=colegio_id)

    def get_permissions(self):
        if self.action in ('create', 'generar_qr', 'generar_qr_simulado', 'checkout_stripe'):
            return [permissions.IsAuthenticated(), SuperadminOPuesto()]
        if self.action in ('update', 'partial_update', 'destroy', 'suspender',
                           'cancelar', 'reactivar'):
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        return [permissions.IsAuthenticated(), PuedeConsultarFacturacion()]

    def create(self, request, *args, **kwargs):
        """Contrata un plan: crea la vigencia con snapshot del plan (PENDIENTE)."""
        entrada = ContratarSuscripcionSerializer(
            data=request.data, context={'request': request},
        )
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        if es_superadmin(request.user):
            if datos.get('colegio') is None:
                raise ValidationError({
                    'colegio': 'Debe indicar el colegio que contrata el plan.',
                })
            colegio = datos['colegio']
        else:
            alcance = resolver_alcance(request.user)
            colegio_id = alcance['colegio_id']
            if datos.get('colegio') is not None and datos['colegio'].pk != colegio_id:
                raise PermissionDenied('No puede contratar planes para otro colegio.')
            colegio = datos.get('colegio') or Colegio.objects.get(pk=colegio_id)

        plan = datos['plan']
        hoy = timezone.localdate()
        fecha_inicio = datos.get('fecha_inicio') or hoy
        if fecha_inicio < hoy:
            raise ValidationError({'fecha_inicio': 'La fecha de inicio no puede estar en el pasado.'})

        with transaction.atomic():
            # Serializa las contrataciones del mismo colegio antes de comprobar el estado.
            colegio = Colegio.objects.select_for_update().get(pk=colegio.pk)
            bloqueada = Suscripcion.objects.filter(colegio=colegio).filter(
                Q(estado__in=[Suscripcion.Estado.PENDIENTE, Suscripcion.Estado.SUSPENDIDA]) |
                Q(estado=Suscripcion.Estado.ACTIVA, fecha_vencimiento__gte=hoy)
            ).first()
            if bloqueada is not None:
                raise ValidationError({'colegio': (
                    f'El colegio ya tiene una suscripción {bloqueada.get_estado_display().lower()}. '
                    'Resuelva la suscripción actual antes de contratar otro plan.'
                )})
            suscripcion = Suscripcion.objects.create(
                colegio=colegio,
                plan=plan,
                precio_periodico=plan.precio,
                moneda=plan.moneda,
                periodicidad=plan.periodicidad,
                modulos_habilitados=list(plan.modulos_habilitados or []),
                limite_usuarios=plan.limite_usuarios,
                limite_unidades=plan.limite_unidades,
                fecha_inicio=fecha_inicio,
                fecha_vencimiento=proximo_vencimiento_contratacion(plan, fecha_inicio),
                estado=Suscripcion.Estado.PENDIENTE,
            )
            _auditar(
                request, accion='CREAR', entidad='SUSCRIPCION',
                descripcion=(
                    f'Contratación del plan {plan.nombre} por el colegio '
                    f'{colegio.nombre}'
                ),
                entidad_id=suscripcion.pk, colegio=colegio,
                cambios={'campos': ['plan', 'fecha_inicio', 'fecha_vencimiento']},
            )
        return Response(
            SuscripcionSerializer(suscripcion).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        if instance.pagos.exists():
            raise ValidationError({
                'detail': (
                    'No se puede eliminar una suscripción con pagos registrados; '
                    'cáncelela para conservar el historial.'
                ),
            })
        instance.delete()

    def _cambiar_estado(self, request, permitidos, nuevo, accion_texto):
        suscripcion = self.get_object()
        if suscripcion.estado not in permitidos:
            raise ValidationError({
                'estado': (
                    f'No se puede {accion_texto} una suscripción '
                    f'{suscripcion.get_estado_display().lower()}.'
                ),
            })
        anterior = suscripcion.estado
        suscripcion.estado = nuevo
        suscripcion.save(update_fields=['estado', 'updated_at'])
        _auditar(
            request, accion='ACTUALIZAR', entidad='SUSCRIPCION',
            descripcion=f'{accion_texto.capitalize()} de suscripción del colegio {suscripcion.colegio.nombre}',
            entidad_id=suscripcion.pk, colegio=suscripcion.colegio,
            cambios={'estado_anterior': anterior, 'estado_nuevo': nuevo},
            accion_bitacora='editar',
        )
        return Response(SuscripcionSerializer(suscripcion).data)

    @action(detail=True, methods=['post'])
    def suspender(self, request, pk=None):
        return self._cambiar_estado(
            request,
            {Suscripcion.Estado.ACTIVA, Suscripcion.Estado.PENDIENTE},
            Suscripcion.Estado.SUSPENDIDA, 'suspender',
        )

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        return self._cambiar_estado(
            request,
            set(Suscripcion.Estado.values) - {Suscripcion.Estado.CANCELADA},
            Suscripcion.Estado.CANCELADA, 'cancelar',
        )

    @action(detail=True, methods=['post'])
    def reactivar(self, request, pk=None):
        suscripcion = self.get_object()
        if suscripcion.estado != Suscripcion.Estado.SUSPENDIDA:
            raise ValidationError({'estado': 'Solo se pueden reactivar suscripciones suspendidas.'})
        if not suscripcion.pagos.filter(resultado=Pago.Resultado.VALIDADO).exists():
            raise ValidationError({'estado': 'La suscripción no tiene un pago validado.'})
        if suscripcion.fecha_vencimiento < timezone.localdate():
            raise ValidationError({
                'estado': (
                    'La suscripción está vencida; registre un pago de renovación '
                    'para reactivarla.'
                ),
            })
        anterior = suscripcion.estado
        suscripcion.estado = Suscripcion.Estado.ACTIVA
        suscripcion.save(update_fields=['estado', 'updated_at'])
        _auditar(
            request, accion='ACTUALIZAR', entidad='SUSCRIPCION',
            descripcion=f'Reactivación de suscripción del colegio {suscripcion.colegio.nombre}',
            entidad_id=suscripcion.pk, colegio=suscripcion.colegio,
            cambios={'estado_anterior': anterior, 'estado_nuevo': suscripcion.estado},
            accion_bitacora='editar',
        )
        return Response(SuscripcionSerializer(suscripcion).data)

    @action(detail=False, methods=['get'], url_path='mi-estado')
    def mi_estado(self, request):
        """Estado de la suscripción del colegio del usuario (o ?colegio= para SA)."""
        if es_superadmin(request.user):
            colegio_id = request.query_params.get('colegio')
            if not colegio_id:
                raise ValidationError({'colegio': 'Indique el colegio con ?colegio=ID.'})
        else:
            colegio_id = servicios.colegio_del_usuario(request.user)
            if colegio_id is None:
                raise PermissionDenied('El usuario no tiene un colegio asociado.')
        return Response(datos_estado_suscripcion(colegio_id))

    @action(detail=True, methods=['post'], url_path='generar-qr')
    def generar_qr(self, request, pk=None):
        suscripcion = self.get_object()
        if servicios.estado_efectivo(suscripcion) not in (Suscripcion.Estado.PENDIENTE, Suscripcion.Estado.VENCIDA):
            raise ValidationError('La suscripción no está pendiente de pago o renovación.')
        if suscripcion.precio_periodico <= 0 or suscripcion.precio_periodico > Decimal('99999999'):
            raise ValidationError('El precio del plan no es válido para un pago QR.')
        if suscripcion.moneda != 'BOB':
            raise ValidationError('El pago QR solo está disponible en bolivianos.')
        # Comprueba la configuración antes de reservar un intento.
        vendis._configuracion()
        with transaction.atomic():
            suscripcion = Suscripcion.objects.select_for_update().get(pk=suscripcion.pk)
            # La suscripción pudo activarse mientras esperábamos el bloqueo.
            if servicios.estado_efectivo(suscripcion) not in (Suscripcion.Estado.PENDIENTE, Suscripcion.Estado.VENCIDA):
                raise ValidationError('La suscripción no está pendiente de pago o renovación.')
            if suscripcion.pagos.filter(metodo=Pago.Metodo.STRIPE, resultado=Pago.Resultado.PENDIENTE).exists():
                raise ValidationError('Existe un pago de Stripe pendiente para esta suscripción.')
            previo = Pago.objects.filter(suscripcion=suscripcion, metodo=Pago.Metodo.PASARELA,
                                         resultado=Pago.Resultado.PENDIENTE).order_by('-id').first()
            if previo:
                if previo.qr_url and previo.qr_expira_at and previo.qr_expira_at > timezone.now():
                    return Response(PagoSerializer(previo).data)
                raise ValidationError('Existe un intento QR pendiente que requiere conciliación antes de generar otro.')
            pago = Pago.objects.create(suscripcion=suscripcion, metodo=Pago.Metodo.PASARELA,
                referencia=f'UE-{uuid4().hex[:20]}', monto=suscripcion.precio_periodico,
                moneda='BOB', fecha=timezone.localdate(), qr_expira_at=timezone.now() + timedelta(minutes=15),
                observacion='Generación QR pendiente de confirmación')
            _auditar(request, accion='CREAR', entidad='PAGO', descripcion=f'Intento QR {pago.pk}',
                     entidad_id=pago.pk, colegio=suscripcion.colegio)
        try:
            qr_id, qr_url = vendis.generar(pago.monto, pago.referencia, pago.qr_expira_at)
            pago.qr_id, pago.qr_url = qr_id, qr_url
            pago.observacion = 'Esperando confirmación de Vendis'
            pago.save(update_fields=['qr_id', 'qr_url', 'observacion', 'updated_at'])
        except Exception:
            # Una respuesta perdida puede corresponder a un QR emitido: no duplicar el cobro.
            pago.observacion = 'Generación incierta; requiere conciliación administrativa'
            pago.save(update_fields=['observacion', 'updated_at'])
            raise
        return Response(PagoSerializer(pago).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='generar-qr-simulado')
    def generar_qr_simulado(self, request, pk=None):
        pago, creado = qr_simulado.generar(self.get_object().pk)
        return Response(
            {**PagoSerializer(pago).data, 'qr_imagen_simulada': qr_simulado.imagen(pago)},
            status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='checkout-stripe')
    def checkout_stripe(self, request, pk=None):
        return Response(stripe_checkout.iniciar_checkout(self.get_object().pk))


class PagoViewSet(viewsets.ModelViewSet):
    """Pagos de suscripciones. Solo un pago VALIDADO activa o renueva.

    Registro manual o pago QR confirmado por la pasarela.
    """

    serializer_class = PagoSerializer
    queryset = Pago.objects.select_related('suscripcion__colegio', 'suscripcion__plan')
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = Pago.objects.select_related(
            'suscripcion__colegio', 'suscripcion__plan',
        ).order_by('-fecha', '-id')
        user = self.request.user
        if es_superadmin(user):
            colegio = self.request.query_params.get('colegio')
            if colegio:
                qs = qs.filter(suscripcion__colegio_id=colegio)
            suscripcion = self.request.query_params.get('suscripcion')
            if suscripcion:
                qs = qs.filter(suscripcion_id=suscripcion)
            resultado = self.request.query_params.get('resultado')
            if resultado in Pago.Resultado.values:
                qs = qs.filter(resultado=resultado)
            return qs
        colegio_id = servicios.colegio_del_usuario(user)
        if colegio_id is None:
            return qs.none()
        qs = qs.filter(suscripcion__colegio_id=colegio_id)
        suscripcion = self.request.query_params.get('suscripcion')
        if suscripcion:
            qs = qs.filter(suscripcion_id=suscripcion)
        return qs

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'validar', 'rechazar'):
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        if self.action in ('list', 'retrieve'):
            return [permissions.IsAuthenticated(), PuedeConsultarFacturacion()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        from aplicaciones.usuarios.privilegios import puede
        if not es_superadmin(request.user) and not puede(request.user, 'suscripcion', 'crear'):
            raise PermissionDenied('No tiene permiso para registrar pagos de suscripción.')
        serializer = PagoSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        if datos['metodo'] == Pago.Metodo.PASARELA:
            raise ValidationError({'metodo': 'Genere el QR desde la suscripción; la pasarela verifica el pago.'})
        if datos['metodo'] == Pago.Metodo.STRIPE:
            raise ValidationError({'metodo': 'Inicia el pago con Stripe desde la suscripción.'})
        if datos['metodo'] == Pago.Metodo.QR_SIMULADO:
            raise ValidationError({'metodo': 'Genera el QR simulado desde la suscripción.'})
        suscripcion = datos['suscripcion']
        moneda = datos.get('moneda') or suscripcion.moneda
        with transaction.atomic():
            pago = serializer.save(
                fecha=datos.get('fecha') or timezone.localdate(),
                moneda=moneda,
                resultado=Pago.Resultado.PENDIENTE,
            )
            _auditar(
                request, accion='CREAR', entidad='PAGO',
                descripcion=(
                    f'Registro de pago {pago.pk} por {pago.monto} {pago.moneda} '
                    f'(suscripción {suscripcion.pk})'
                ),
                entidad_id=pago.pk, colegio=suscripcion.colegio,
                cambios={'campos': ['suscripcion', 'metodo', 'monto']},
            )
        return Response(PagoSerializer(pago).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        raise ValidationError('Los pagos registrados no se pueden modificar.')

    @action(detail=True, methods=['post'], url_path='simular-pago-qr')
    def simular_pago_qr(self, request, pk=None):
        from aplicaciones.usuarios.privilegios import puede
        if not es_superadmin(request.user) and not puede(request.user, 'suscripcion', 'crear'):
            raise PermissionDenied('No tiene permiso para gestionar pagos de suscripción.')
        return Response(PagoSerializer(qr_simulado.confirmar(self.get_object(), request)).data)

    @action(detail=True, methods=['post'], url_path='consultar-qr')
    def consultar_qr(self, request, pk=None):
        from aplicaciones.usuarios.privilegios import puede
        if not es_superadmin(request.user) and not puede(request.user, 'suscripcion', 'crear'):
            raise PermissionDenied('No tiene permiso para gestionar pagos de suscripción.')
        pago = self.get_object()
        if pago.metodo != Pago.Metodo.PASARELA or not pago.qr_id:
            raise ValidationError('Este pago no tiene un QR verificable.')
        return self._consultar_pago_qr(request, pago)


    @staticmethod
    def _consultar_pago_qr(request, pago):
        if pago.resultado != Pago.Resultado.PENDIENTE:
            return Response(PagoSerializer(pago).data)
        data = vendis.consultar(pago.qr_id)
        estado = str(data.get('status', '')).strip().upper()
        if estado == 'PAGADO':
            pagos = data.get('payments')
            detalle = pagos[0] if isinstance(pagos, list) and len(pagos) == 1 and isinstance(pagos[0], dict) else {}
            try:
                monto = Decimal(str(detalle['payment_amount']))
                fecha = parse_datetime(str(detalle['payment_date']))
                if fecha and timezone.is_naive(fecha):
                    fecha = timezone.make_aware(fecha, ZoneInfo('America/La_Paz'))
                valido = monto.is_finite() and monto == pago.monto and fecha and pago.qr_expira_at and fecha <= pago.qr_expira_at
            except (KeyError, InvalidOperation, ValueError, TypeError):
                valido = False
            if not valido:
                pago.observacion = 'Pago informado con datos inconsistentes; requiere conciliación'
                pago.save(update_fields=['observacion', 'updated_at'])
                raise ValidationError('El pago requiere conciliación: monto o fecha inválidos.')
            with transaction.atomic():
                pago = Pago.objects.select_for_update().select_related('suscripcion__colegio').get(pk=pago.pk)
                suscripcion = Suscripcion.objects.select_for_update().get(pk=pago.suscripcion_id)
                if pago.resultado == Pago.Resultado.PENDIENTE:
                    if servicios.estado_efectivo(suscripcion) not in (Suscripcion.Estado.PENDIENTE, Suscripcion.Estado.VENCIDA):
                        raise ValidationError('La suscripción requiere conciliación administrativa.')
                    pago.suscripcion = suscripcion
                    pago.resultado = Pago.Resultado.VALIDADO
                    pago.validado_at = timezone.now()
                    pago.observacion = 'Pago confirmado por Vendis'
                    pago.save(update_fields=['resultado', 'validado_at', 'observacion', 'updated_at'])
                    servicios.aplicar_pago_validado(pago)
                    _auditar(request, accion='ACTUALIZAR', entidad='PAGO', descripcion=f'Pago QR {pago.pk} confirmado por Vendis',
                             entidad_id=pago.pk, colegio=suscripcion.colegio, cambios={'resultado': 'VALIDADO'}, accion_bitacora='editar')
        elif estado not in ('PENDIENTE', 'PENDING'):
            pago.observacion = 'Estado de Vendis requiere conciliación administrativa'
            pago.save(update_fields=['observacion', 'updated_at'])
        return Response(PagoSerializer(pago).data)

    @action(detail=True, methods=['post'])
    def validar(self, request, pk=None):
        """Valida un pago pendiente: activa o renueva la suscripción."""
        pago = self.get_object()
        if pago.metodo == Pago.Metodo.PASARELA:
            raise ValidationError('Los pagos QR solo se validan mediante Vendis.')
        if pago.metodo == Pago.Metodo.STRIPE:
            raise ValidationError('Stripe confirma este pago automáticamente.')
        if pago.metodo == Pago.Metodo.QR_SIMULADO:
            raise ValidationError('Confirma el QR simulado desde la suscripción.')
        if pago.resultado != Pago.Resultado.PENDIENTE:
            raise ValidationError({'resultado': 'Solo se pueden validar pagos pendientes.'})
        with transaction.atomic():
            suscripcion = Suscripcion.objects.select_for_update().get(pk=pago.suscripcion_id)
            pago = Pago.objects.select_for_update().get(pk=pago.pk)
            if pago.resultado != Pago.Resultado.PENDIENTE:
                raise ValidationError({'resultado': 'Solo se pueden validar pagos pendientes.'})
            importe_valido = pago.monto == suscripcion.precio_periodico or (
                suscripcion.precio_periodico == 0 and pago.monto > 0
            )
            if not importe_valido or pago.moneda != suscripcion.moneda:
                raise ValidationError('El monto y la moneda no son válidos para la suscripción contratada.')
            if suscripcion.pagos.filter(metodo=Pago.Metodo.STRIPE, resultado=Pago.Resultado.PENDIENTE).exists():
                raise ValidationError('Existe un pago de Stripe pendiente para esta suscripción.')
            pago.suscripcion = suscripcion
            estado_anterior = suscripcion.estado
            pago.resultado = Pago.Resultado.VALIDADO
            pago.validado_por = request.user
            pago.validado_at = timezone.now()
            pago.save(update_fields=['resultado', 'validado_por', 'validado_at', 'updated_at'])
            servicios.aplicar_pago_validado(pago)
            _auditar(
                request, accion='ACTUALIZAR', entidad='PAGO',
                descripcion=f'Validación del pago {pago.pk}',
                entidad_id=pago.pk, colegio=pago.suscripcion.colegio,
                cambios={'resultado': 'VALIDADO'},
                accion_bitacora='editar',
            )
            if pago.suscripcion.estado != estado_anterior:
                _auditar(
                    request, accion='ACTUALIZAR', entidad='SUSCRIPCION',
                    descripcion=(
                        f'Activación o renovación de suscripción tras validar el pago {pago.pk}'
                    ),
                    entidad_id=pago.suscripcion_id, colegio=pago.suscripcion.colegio,
                    cambios={
                        'estado_anterior': estado_anterior,
                        'estado_nuevo': pago.suscripcion.estado,
                    },
                    accion_bitacora='editar',
                )
        return Response(PagoSerializer(pago).data)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        pago = self.get_object()
        if pago.metodo == Pago.Metodo.PASARELA:
            raise ValidationError('Los pagos QR requieren conciliación con Vendis.')
        if pago.metodo == Pago.Metodo.STRIPE:
            raise ValidationError('Stripe confirma el estado de este pago automáticamente.')
        if pago.metodo == Pago.Metodo.QR_SIMULADO:
            raise ValidationError('El QR simulado caduca automáticamente.')
        if pago.resultado != Pago.Resultado.PENDIENTE:
            raise ValidationError({'resultado': 'Solo se pueden rechazar pagos pendientes.'})
        motivo = str(request.data.get('motivo', '') or '').strip()
        pago.resultado = Pago.Resultado.RECHAZADO
        if motivo:
            pago.observacion = motivo[:255]
        pago.save(update_fields=['resultado', 'observacion', 'updated_at'])
        _auditar(
            request, accion='ACTUALIZAR', entidad='PAGO',
            descripcion=f'Rechazo del pago {pago.pk}', entidad_id=pago.pk,
            colegio=pago.suscripcion.colegio,
            cambios={'resultado': 'RECHAZADO', 'motivo': motivo[:200] or None},
            accion_bitacora='editar',
        )
        return Response(PagoSerializer(pago).data)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def notificacion_vendis(request):
    token = settings.VENDIS_WEBHOOK_TOKEN
    auth = request.headers.get('Authorization', '')
    if len(token) < 32 or not compare_digest(auth.encode('utf-8'), ('Bearer ' + token).encode('utf-8')):
        return Response({'detail': 'No autorizado.'}, status=403)
    qr_id = request.data.get('qr_id')
    if not isinstance(qr_id, (str, int)) or isinstance(qr_id, bool) or not str(qr_id).strip() or len(str(qr_id)) > 100:
        return Response({'detail': 'Referencia inválida.'}, status=400)
    pago = Pago.objects.filter(qr_id=str(qr_id), metodo=Pago.Metodo.PASARELA).first()
    if pago is None:
        from aplicaciones.finanzas.qr import procesar_notificacion
        if procesar_notificacion(str(qr_id)):
            return Response({'detail': 'Notificación procesada.'})
        return Response({'detail': 'QR no asociado; requiere conciliación.'}, status=503)
    PagoViewSet._consultar_pago_qr(request, pago)
    return Response({'detail': 'Notificación procesada.'})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def notificacion_stripe(request):
    evento = stripe_checkout.obtener_evento(request.body, request.headers.get('Stripe-Signature', ''))
    stripe_checkout.procesar_evento(evento, request)
    return Response(status=status.HTTP_204_NO_CONTENT)

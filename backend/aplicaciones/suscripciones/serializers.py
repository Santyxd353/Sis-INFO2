from rest_framework import serializers
from django.conf import settings

from aplicaciones.institucion.models import Colegio
from . import qr_simulado, vendis
from .models import MetodoPago, MetodoPagoColegio, Pago, Plan, Suscripcion
from .servicios import calcular_vencimiento, estado_efectivo


class PlanSerializer(serializers.ModelSerializer):
    qr_simulado_disponible = serializers.SerializerMethodField()
    periodicidad_display = serializers.CharField(
        source='get_periodicidad_display', read_only=True,
    )
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Plan
        fields = [
            'id', 'nombre', 'descripcion', 'precio', 'moneda', 'periodicidad',
            'periodicidad_display', 'modulos_habilitados', 'limite_usuarios',
            'limite_unidades', 'estado', 'estado_display',
            'created_at', 'updated_at', 'qr_simulado_disponible',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_qr_simulado_disponible(self, plan):
        return qr_simulado.plan_habilitado(plan.pk, plan.precio)

    def validate_precio(self, value):
        if value < 0:
            raise serializers.ValidationError('El precio no puede ser negativo.')
        return value

    def validate_moneda(self, value):
        value = value.upper()
        if value not in {'BOB', 'USD'}:
            raise serializers.ValidationError('Seleccione BOB o USD.')
        return value

    def validate_modulos_habilitados(self, value):
        if value is None:
            return []
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise serializers.ValidationError(
                'Los módulos habilitados deben ser una lista de nombres.',
            )
        return [item.strip() for item in value]


class MetodoPagoSerializer(serializers.ModelSerializer):
    modo_prueba = serializers.SerializerMethodField()
    disponible = serializers.SerializerMethodField()

    class Meta:
        model = MetodoPago
        fields = ['id', 'codigo', 'nombre', 'descripcion', 'activo', 'banco', 'titular', 'numero_cuenta', 'tipo_cuenta', 'moneda_cuenta', 'instrucciones', 'qr_imagen', 'creado_at', 'actualizado_at', 'modo_prueba', 'disponible']
        read_only_fields = ['creado_at', 'actualizado_at']

    def get_modo_prueba(self, metodo):
        from .stripe_checkout import modo_prueba
        return metodo.codigo == MetodoPago.Codigo.QR_SIMULADO or (
            metodo.codigo == MetodoPago.Codigo.STRIPE and modo_prueba()
        )

    def get_disponible(self, metodo):
        from .stripe_checkout import configurado
        if not metodo.activo:
            return False
        if metodo.codigo == MetodoPago.Codigo.STRIPE:
            return configurado()
        if metodo.codigo == MetodoPago.Codigo.PASARELA:
            return vendis.configurado()
        if metodo.codigo == MetodoPago.Codigo.QR_SIMULADO:
            return bool(settings.QR_DEMO_PLAN_IDS)
        return True

    def validate_moneda_cuenta(self, value):
        value = (value or '').upper()
        if value and value not in {'BOB', 'USD'}:
            raise serializers.ValidationError('La moneda de la cuenta debe ser BOB o USD.')
        return value


class MetodoPagoColegioSerializer(serializers.ModelSerializer):
    metodo_nombre = serializers.CharField(source='metodo.nombre', read_only=True)
    codigo = serializers.CharField(source='metodo.codigo', read_only=True)
    colegio_nombre = serializers.CharField(source='colegio.nombre', read_only=True)

    class Meta:
        model = MetodoPagoColegio
        fields = ['id', 'colegio', 'colegio_nombre', 'metodo', 'metodo_nombre', 'codigo', 'nombre_visible', 'banco', 'titular', 'numero_cuenta', 'tipo_cuenta', 'moneda_cuenta', 'instrucciones', 'qr_imagen', 'activo', 'creado_at', 'actualizado_at']
        read_only_fields = ['colegio', 'colegio_nombre', 'metodo_nombre', 'codigo', 'creado_at', 'actualizado_at']

    def validate_metodo(self, value):
        if not value.activo:
            raise serializers.ValidationError('El método no está habilitado por la plataforma.')
        return value

    def validate_moneda_cuenta(self, value):
        value = (value or '').upper()
        if value and value not in {'BOB', 'USD'}:
            raise serializers.ValidationError('La moneda de la cuenta debe ser BOB o USD.')
        return value


class SuscripcionSerializer(serializers.ModelSerializer):
    colegio_nombre = serializers.CharField(source='colegio.nombre', read_only=True)
    plan_nombre = serializers.CharField(source='plan.nombre', read_only=True)
    periodicidad_display = serializers.CharField(
        source='get_periodicidad_display', read_only=True,
    )
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    estado_efectivo = serializers.SerializerMethodField()
    qr_simulado_disponible = serializers.SerializerMethodField()

    class Meta:
        model = Suscripcion
        fields = [
            'id', 'colegio', 'colegio_nombre', 'plan', 'plan_nombre',
            'precio_periodico', 'moneda', 'periodicidad', 'periodicidad_display',
            'modulos_habilitados', 'limite_usuarios', 'limite_unidades',
            'fecha_inicio', 'fecha_vencimiento', 'estado', 'estado_display',
            'estado_efectivo', 'created_at', 'updated_at', 'qr_simulado_disponible',
        ]
        read_only_fields = [
            'colegio', 'precio_periodico', 'moneda', 'periodicidad', 'modulos_habilitados',
            'limite_usuarios', 'limite_unidades', 'estado',
            'created_at', 'updated_at',
        ]

    def get_estado_efectivo(self, obj):
        return estado_efectivo(obj)

    def get_qr_simulado_disponible(self, suscripcion):
        return qr_simulado.plan_habilitado(suscripcion.plan_id, suscripcion.precio_periodico)


class ContratarSuscripcionSerializer(serializers.Serializer):
    """Entrada para contratar un plan (la suscripción nace PENDIENTE de pago)."""

    colegio = serializers.PrimaryKeyRelatedField(
        queryset=Colegio.objects.all(), required=False,
    )
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all())
    fecha_inicio = serializers.DateField(required=False)

    def validate_plan(self, value):
        if value.estado != Plan.Estado.ACTIVO or value.eliminado_at is not None:
            raise serializers.ValidationError('El plan seleccionado no está activo.')
        return value


class PagoSerializer(serializers.ModelSerializer):
    suscripcion_colegio_nombre = serializers.CharField(
        source='suscripcion.colegio.nombre', read_only=True,
    )
    suscripcion_plan_nombre = serializers.CharField(
        source='suscripcion.plan.nombre', read_only=True,
    )
    metodo_display = serializers.CharField(source='get_metodo_display', read_only=True)
    resultado_display = serializers.CharField(
        source='get_resultado_display', read_only=True,
    )
    validado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Pago
        fields = [
            'id', 'suscripcion', 'suscripcion_colegio_nombre',
            'suscripcion_plan_nombre', 'metodo', 'metodo_display', 'referencia',
            'monto', 'moneda', 'fecha', 'resultado', 'resultado_display',
            'observacion', 'validado_por', 'validado_por_nombre', 'validado_at',
            'qr_id', 'qr_url', 'qr_expira_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'resultado', 'validado_por', 'validado_at', 'created_at', 'updated_at',
            'qr_id', 'qr_url', 'qr_expira_at',
        ]
        extra_kwargs = {
            # La fecha se completa con el día de registro cuando no se envía.
            'fecha': {'required': False},
        }

    def get_validado_por_nombre(self, obj):
        if obj.validado_por is None:
            return None
        return f'{obj.validado_por.nombre} {obj.validado_por.apellido}'

    def validate_monto(self, value):
        if value <= 0:
            raise serializers.ValidationError('El monto debe ser mayor a cero.')
        return value

    def validate_suscripcion(self, value):
        from aplicaciones.usuarios.tenancy import es_superadmin
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not es_superadmin(user):
            from .servicios import colegio_del_usuario
            colegio_id = colegio_del_usuario(user)
            if colegio_id is None or value.colegio_id != colegio_id:
                raise serializers.ValidationError(
                    'No puede registrar pagos de una suscripción de otro colegio.',
                )
        return value

    def validate_metodo(self, value):
        if not MetodoPago.objects.filter(codigo=value, activo=True).exists():
            raise serializers.ValidationError('El método de pago seleccionado no está disponible.')
        return value


class EstadoSuscripcionSerializer(serializers.Serializer):
    """Vista del colegio sobre su propia suscripción (HU-SE01 regla 3)."""

    tiene_suscripcion = serializers.BooleanField()
    suscripcion = serializers.IntegerField(allow_null=True)
    plan = serializers.CharField(allow_null=True)
    estado = serializers.CharField()
    estado_display = serializers.CharField(allow_null=True)
    fecha_inicio = serializers.DateField(allow_null=True)
    fecha_vencimiento = serializers.DateField(allow_null=True)
    precio_periodico = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    moneda = serializers.CharField(allow_null=True)
    periodicidad = serializers.CharField(allow_null=True)
    periodicidad_display = serializers.CharField(allow_null=True)
    modulos_habilitados = serializers.ListField(
        child=serializers.CharField(), allow_empty=True,
    )
    limite_usuarios = serializers.IntegerField(allow_null=True)
    limite_unidades = serializers.IntegerField(allow_null=True)
    suscripcion_activa = serializers.BooleanField()
    restriccion = serializers.CharField(allow_null=True)


def datos_estado_suscripcion(colegio):
    """Construye la respuesta del estado de suscripción de un colegio."""
    from .servicios import (
        restriccion_activa, suscripcion_activa, suscripcion_mas_reciente,
    )
    suscripcion = suscripcion_mas_reciente(colegio)
    activa = suscripcion_activa(colegio) is not None
    restriccion = restriccion_activa(colegio)
    base = {
        'tiene_suscripcion': suscripcion is not None,
        'suscripcion': suscripcion.pk if suscripcion else None,
        'plan': suscripcion.plan.nombre if suscripcion else None,
        'estado': estado_efectivo(suscripcion),
        'estado_display': suscripcion.get_estado_display() if suscripcion else None,
        'fecha_inicio': suscripcion.fecha_inicio if suscripcion else None,
        'fecha_vencimiento': suscripcion.fecha_vencimiento if suscripcion else None,
        'precio_periodico': suscripcion.precio_periodico if suscripcion else None,
        'moneda': suscripcion.moneda if suscripcion else None,
        'periodicidad': suscripcion.periodicidad if suscripcion else None,
        'periodicidad_display': (
            suscripcion.get_periodicidad_display() if suscripcion else None
        ),
        'modulos_habilitados': list(suscripcion.modulos_habilitados or []) if suscripcion else [],
        'limite_usuarios': suscripcion.limite_usuarios if suscripcion else None,
        'limite_unidades': suscripcion.limite_unidades if suscripcion else None,
        'suscripcion_activa': activa,
        'restriccion': restriccion,
    }
    return EstadoSuscripcionSerializer(base).data


def proximo_vencimiento_contratacion(plan, fecha_inicio):
    return calcular_vencimiento(fecha_inicio, plan.periodicidad)

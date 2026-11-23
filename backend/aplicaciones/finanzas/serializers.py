from decimal import Decimal

from rest_framework import serializers

from aplicaciones.usuarios.feature_access import full_name

from .fechas import hoy
from .models import AsignacionBeca, Beca, CuotaPlan, DetallePago, ObligacionPago, Pago, PlanPago, SolicitudQR

CAMPOS_BLOQUEADOS_PLAN = ('unidad_educativa', 'calendario_academico', 'nivel_educativo', 'monto_total', 'numero_cuotas')


class CuotaPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuotaPlan
        fields = ('id', 'numero', 'concepto', 'monto', 'fecha_vencimiento')


class PlanPagoSerializer(serializers.ModelSerializer):
    unidad_nombre = serializers.CharField(source='unidad_educativa.nombre', read_only=True)
    gestion = serializers.IntegerField(source='calendario_academico.año', read_only=True)
    nivel_display = serializers.CharField(source='get_nivel_educativo_display', read_only=True)
    cuotas = CuotaPlanSerializer(many=True, read_only=True)
    estudiantes_asignados = serializers.SerializerMethodField()

    class Meta:
        model = PlanPago
        fields = (
            'id', 'unidad_educativa', 'unidad_nombre', 'calendario_academico', 'gestion',
            'nombre', 'descripcion', 'nivel_educativo', 'nivel_display', 'monto_total',
            'numero_cuotas', 'moneda', 'estado', 'cuotas', 'estudiantes_asignados',
            'created_at', 'updated_at',
        )
        read_only_fields = ('estado', 'created_at', 'updated_at')

    def get_estudiantes_asignados(self, plan):
        anotado = getattr(plan, 'num_estudiantes', None)
        if anotado is not None:
            return anotado
        return ObligacionPago.objects.filter(cuota__plan=plan).values('estudiante_id').distinct().count()

    def validate_nombre(self, value):
        limpio = ' '.join(value.split())
        if not limpio:
            raise serializers.ValidationError('El nombre es obligatorio.')
        return limpio

    def validate_numero_cuotas(self, value):
        if not 1 <= value <= 12:
            raise serializers.ValidationError('El número de cuotas debe estar entre 1 y 12.')
        return value

    def validate_monto_total(self, value):
        if value <= 0:
            raise serializers.ValidationError('El monto total debe ser mayor a cero.')
        return value

    def validate(self, attrs):
        plan = self.instance
        if plan and plan.estado != PlanPago.Estado.BORRADOR:
            cambiados = [
                campo for campo in CAMPOS_BLOQUEADOS_PLAN
                if campo in attrs and attrs[campo] != getattr(plan, campo)
            ]
            if cambiados:
                raise serializers.ValidationError(
                    {'detail': 'Un plan activo o inactivo solo permite editar nombre y descripción.'},
                )
        unidad = attrs.get('unidad_educativa', getattr(plan, 'unidad_educativa', None))
        calendario = attrs.get('calendario_academico', getattr(plan, 'calendario_academico', None))
        if unidad and calendario and calendario.unidad_educativa_id != unidad.pk:
            raise serializers.ValidationError(
                {'calendario_academico': 'La gestión no pertenece a la unidad educativa.'},
            )
        return attrs


class GenerarCuotasSerializer(serializers.Serializer):
    fecha_primer_vencimiento = serializers.DateField()

    def validate_fecha_primer_vencimiento(self, value):
        calendario = self.context['plan'].calendario_academico
        if not calendario.fecha_inicio <= value <= calendario.fecha_fin:
            raise serializers.ValidationError('La fecha debe estar dentro de la gestión del plan.')
        return value


class AsignarPlanSerializer(serializers.Serializer):
    estudiantes = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=False, max_length=500,
    )
    curso = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if bool(attrs.get('estudiantes')) == bool(attrs.get('curso')):
            raise serializers.ValidationError({'detail': 'Indique una lista de estudiantes o un curso.'})
        return attrs


class BecaSerializer(serializers.ModelSerializer):
    unidad_nombre = serializers.CharField(source='unidad_educativa.nombre', read_only=True)
    tipo_descuento_display = serializers.CharField(source='get_tipo_descuento_display', read_only=True)
    asignaciones_vigentes = serializers.SerializerMethodField()

    class Meta:
        model = Beca
        fields = (
            'id', 'unidad_educativa', 'unidad_nombre', 'nombre', 'descripcion', 'tipo_descuento',
            'tipo_descuento_display', 'valor', 'estado', 'asignaciones_vigentes', 'created_at', 'updated_at',
        )
        read_only_fields = ('estado', 'created_at', 'updated_at')

    def get_asignaciones_vigentes(self, beca):
        anotado = getattr(beca, 'num_vigentes', None)
        if anotado is not None:
            return anotado
        return beca.asignaciones.filter(estado=AsignacionBeca.Estado.VIGENTE).count()

    def validate_nombre(self, value):
        limpio = ' '.join(value.split())
        if not limpio:
            raise serializers.ValidationError('El nombre es obligatorio.')
        return limpio

    def validate(self, attrs):
        if self.instance and 'unidad_educativa' in attrs and attrs['unidad_educativa'] != self.instance.unidad_educativa:
            raise serializers.ValidationError({'unidad_educativa': 'No se puede cambiar la unidad de una beca.'})
        tipo = attrs.get('tipo_descuento', getattr(self.instance, 'tipo_descuento', None))
        valor = attrs.get('valor', getattr(self.instance, 'valor', None))
        if valor is not None and valor <= 0:
            raise serializers.ValidationError({'valor': 'El valor debe ser mayor a cero.'})
        if tipo == Beca.TipoDescuento.PORCENTAJE and valor is not None and valor > 100:
            raise serializers.ValidationError({'valor': 'El porcentaje no puede superar 100.'})
        return attrs


class AsignacionBecaSerializer(serializers.ModelSerializer):
    beca_nombre = serializers.CharField(source='beca.nombre', read_only=True)
    tipo_descuento = serializers.CharField(source='beca.tipo_descuento', read_only=True)
    valor = serializers.DecimalField(source='beca.valor', max_digits=10, decimal_places=2, read_only=True)
    estudiante_nombre = serializers.SerializerMethodField()
    curso_nombre = serializers.CharField(source='estudiante.curso.nombre', read_only=True, default=None)
    gestion = serializers.IntegerField(source='calendario_academico.año', read_only=True)
    asignado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = AsignacionBeca
        fields = (
            'id', 'beca', 'beca_nombre', 'tipo_descuento', 'valor', 'estudiante', 'estudiante_nombre',
            'curso_nombre', 'calendario_academico', 'gestion', 'motivo', 'estado', 'asignado_por_nombre',
            'motivo_revocacion', 'revocado_at', 'created_at',
        )
        read_only_fields = ('estado', 'motivo_revocacion', 'revocado_at', 'created_at')

    def get_estudiante_nombre(self, asignacion):
        return full_name(asignacion.estudiante.usuario)

    def get_asignado_por_nombre(self, asignacion):
        return full_name(asignacion.asignado_por)

    def validate_motivo(self, value):
        if not value.strip():
            raise serializers.ValidationError('El motivo es obligatorio.')
        return value.strip()

    def validate(self, attrs):
        beca, estudiante = attrs['beca'], attrs['estudiante']
        calendario = attrs['calendario_academico']
        if beca.estado != Beca.Estado.ACTIVO:
            raise serializers.ValidationError({'beca': 'La beca está inactiva.'})
        if estudiante.unidad_id != beca.unidad_educativa_id:
            raise serializers.ValidationError({'estudiante': 'El estudiante no pertenece a la unidad de la beca.'})
        if calendario.unidad_educativa_id != beca.unidad_educativa_id:
            raise serializers.ValidationError({'calendario_academico': 'La gestión no pertenece a la unidad de la beca.'})
        if AsignacionBeca.objects.filter(
            estudiante=estudiante, calendario_academico=calendario, estado=AsignacionBeca.Estado.VIGENTE,
        ).exists():
            raise serializers.ValidationError(
                {'estudiante': 'El estudiante ya tiene una beca vigente en esta gestión. Revóquela primero.'},
            )
        return attrs


class RevocarBecaSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=500)

    def validate_motivo(self, value):
        if not value.strip():
            raise serializers.ValidationError('El motivo es obligatorio.')
        return value.strip()


class ObligacionPagoSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.SerializerMethodField()
    curso_nombre = serializers.CharField(source='estudiante.curso.nombre', read_only=True, default=None)
    plan = serializers.IntegerField(source='cuota.plan_id', read_only=True)
    plan_nombre = serializers.CharField(source='cuota.plan.nombre', read_only=True)
    gestion = serializers.IntegerField(source='cuota.plan.calendario_academico.año', read_only=True)
    numero_cuota = serializers.IntegerField(source='cuota.numero', read_only=True)
    concepto = serializers.CharField(source='cuota.concepto', read_only=True)
    beca_nombre = serializers.CharField(source='asignacion_beca.beca.nombre', read_only=True, default=None)
    vencida = serializers.BooleanField(read_only=True)
    saldo = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ObligacionPago
        fields = (
            'id', 'estudiante', 'estudiante_nombre', 'curso_nombre', 'plan', 'plan_nombre', 'gestion',
            'numero_cuota', 'concepto', 'monto_original', 'descuento', 'monto_final', 'monto_pagado', 'saldo',
            'beca_nombre', 'fecha_vencimiento', 'estado', 'vencida', 'motivo_anulacion', 'created_at',
        )
        read_only_fields = fields

    def get_estudiante_nombre(self, obligacion):
        return full_name(obligacion.estudiante.usuario)


class AnularObligacionSerializer(RevocarBecaSerializer):
    pass


class DetallePagoSerializer(serializers.ModelSerializer):
    concepto = serializers.CharField(source='obligacion.cuota.concepto', read_only=True)
    plan_nombre = serializers.CharField(source='obligacion.cuota.plan.nombre', read_only=True)

    class Meta:
        model = DetallePago
        fields = ('id', 'obligacion', 'concepto', 'plan_nombre', 'monto')


class PagoSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.SerializerMethodField()
    curso_nombre = serializers.CharField(source='estudiante.curso.nombre', read_only=True, default=None)
    metodo_display = serializers.CharField(source='get_metodo_display', read_only=True)
    registrado_por_nombre = serializers.SerializerMethodField()
    detalles = DetallePagoSerializer(many=True, read_only=True)

    class Meta:
        model = Pago
        fields = (
            'id', 'unidad_educativa', 'estudiante', 'estudiante_nombre', 'curso_nombre', 'numero_recibo',
            'fecha_pago', 'monto', 'metodo', 'metodo_display', 'referencia', 'observaciones', 'estado',
            'registrado_por_nombre', 'motivo_anulacion', 'anulado_at', 'detalles', 'created_at',
        )
        read_only_fields = fields

    def get_estudiante_nombre(self, pago):
        return full_name(pago.estudiante.usuario)

    def get_registrado_por_nombre(self, pago):
        return full_name(pago.registrado_por)


class RegistrarPagoSerializer(serializers.Serializer):
    estudiante = serializers.IntegerField(min_value=1)
    monto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    metodo = serializers.ChoiceField(choices=Pago.Metodo.choices)
    fecha_pago = serializers.DateField(required=False)
    referencia = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    observaciones = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    obligaciones = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=False, max_length=24,
    )

    def validate_fecha_pago(self, value):
        if value > hoy():
            raise serializers.ValidationError('La fecha de pago no puede ser futura.')
        return value

    def validate(self, attrs):
        if attrs['metodo'] in (Pago.Metodo.TRANSFERENCIA, Pago.Metodo.QR) and not attrs['referencia'].strip():
            raise serializers.ValidationError({'referencia': 'Indique el número de operación del pago.'})
        return attrs


class ParametrosSimulacionSerializer(serializers.Serializer):
    desde = serializers.DateField()
    hasta = serializers.DateField()
    credito_fiscal = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'), default=Decimal('0.00'))
    tasa_iva = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'), default=Decimal('13.00'))
    tasa_it = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'), default=Decimal('3.00'))

    def validate(self, attrs):
        if attrs['hasta'] < attrs['desde']:
            raise serializers.ValidationError({'hasta': 'La fecha final no puede ser anterior a la inicial.'})
        if (attrs['hasta'] - attrs['desde']).days > 366:
            raise serializers.ValidationError({'hasta': 'El rango no puede superar un año.'})
        return attrs


class EstudianteElegibleSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='pk')
    nombre = serializers.SerializerMethodField()
    rude = serializers.CharField()
    curso = serializers.IntegerField(source='curso_id', allow_null=True)
    curso_nombre = serializers.CharField(source='curso.nombre', default=None)

    def get_nombre(self, estudiante):
        return full_name(estudiante.usuario)


class SolicitudQRSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.SerializerMethodField()
    curso_nombre = serializers.CharField(source='estudiante.curso.nombre', read_only=True, default=None)
    conceptos = serializers.SerializerMethodField()
    qr_url = serializers.SerializerMethodField()
    simulado = serializers.SerializerMethodField()
    conciliacion = serializers.SerializerMethodField()
    numero_recibo = serializers.IntegerField(source='pago.numero_recibo', read_only=True, default=None)
    solicitado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudQR
        fields = (
            'id', 'unidad_educativa', 'estudiante', 'estudiante_nombre', 'curso_nombre', 'conceptos', 'monto',
            'qr_id', 'qr_url', 'simulado', 'expira_at', 'estado', 'conciliacion', 'pago', 'numero_recibo',
            'monto_reportado', 'observacion', 'solicitado_por_nombre', 'verificado_at', 'created_at',
        )
        read_only_fields = fields

    def get_estudiante_nombre(self, solicitud):
        return full_name(solicitud.estudiante.usuario)

    def get_solicitado_por_nombre(self, solicitud):
        return full_name(solicitud.solicitado_por)

    def get_conceptos(self, solicitud):
        return [o.cuota.concepto for o in solicitud.obligaciones.all()]

    def get_qr_url(self, solicitud):
        request = self.context.get('request')
        if solicitud.qr_url.startswith('/') and request is not None:
            return request.build_absolute_uri(solicitud.qr_url)
        return solicitud.qr_url

    def get_simulado(self, solicitud):
        from .pasarela import es_qr_simulado
        return es_qr_simulado(solicitud.qr_id)

    def get_conciliacion(self, solicitud):
        from .qr import estado_conciliacion
        return estado_conciliacion(solicitud)


class CrearSolicitudQRSerializer(serializers.Serializer):
    estudiante = serializers.IntegerField(min_value=1)
    obligaciones = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=False, max_length=24,
    )


class ResolverSolicitudQRSerializer(RevocarBecaSerializer):
    accion = serializers.ChoiceField(choices=('aplicar', 'descartar'))

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from aplicaciones.academico.models import Grado

from .fechas import hoy


class PlanPago(models.Model):
    """HU-22: plan de pensiones de una gestión, dividido en cuotas."""

    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    unidad_educativa = models.ForeignKey(
        'institucion.UnidadEducativa', on_delete=models.PROTECT, related_name='planes_pago',
    )
    calendario_academico = models.ForeignKey(
        'calendario.CalendarioAcademico', on_delete=models.PROTECT, related_name='planes_pago',
    )
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    nivel_educativo = models.CharField(
        max_length=3, choices=Grado.NIVELES_EDUCATIVOS, null=True, blank=True,
        help_text='Vacío: el plan aplica a todos los niveles de la unidad.',
    )
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    numero_cuotas = models.PositiveSmallIntegerField()
    moneda = models.CharField(max_length=3, default='BOB')
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planes_pago_creados',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'finanzas_plan_pago'
        ordering = ['-calendario_academico__año', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['calendario_academico', 'nombre'], name='uq_plan_pago_calendario_nombre'),
            models.CheckConstraint(condition=Q(monto_total__gt=0), name='ck_plan_pago_monto'),
            models.CheckConstraint(
                condition=Q(numero_cuotas__gte=1, numero_cuotas__lte=12), name='ck_plan_pago_cuotas',
            ),
        ]

    def __str__(self):
        return f'{self.nombre} ({self.calendario_academico.año})'


class CuotaPlan(models.Model):
    plan = models.ForeignKey(PlanPago, on_delete=models.CASCADE, related_name='cuotas')
    numero = models.PositiveSmallIntegerField()
    concepto = models.CharField(max_length=80)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_vencimiento = models.DateField()

    class Meta:
        db_table = 'finanzas_cuota_plan'
        ordering = ['plan_id', 'numero']
        constraints = [
            models.UniqueConstraint(fields=['plan', 'numero'], name='uq_cuota_plan_numero'),
            models.CheckConstraint(condition=Q(monto__gt=0), name='ck_cuota_plan_monto'),
        ]

    def __str__(self):
        return f'{self.plan} - {self.concepto}'


class Beca(models.Model):
    """HU-23: tipo de beca o descuento que la unidad puede otorgar."""

    class TipoDescuento(models.TextChoices):
        PORCENTAJE = 'PORCENTAJE', 'Porcentaje'
        MONTO_FIJO = 'MONTO_FIJO', 'Monto fijo por cuota'

    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    unidad_educativa = models.ForeignKey(
        'institucion.UnidadEducativa', on_delete=models.PROTECT, related_name='becas',
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    tipo_descuento = models.CharField(max_length=10, choices=TipoDescuento.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'finanzas_beca'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['unidad_educativa', 'nombre'], name='uq_beca_unidad_nombre'),
            models.CheckConstraint(condition=Q(valor__gt=0), name='ck_beca_valor'),
            models.CheckConstraint(
                condition=~Q(tipo_descuento='PORCENTAJE') | Q(valor__lte=100), name='ck_beca_porcentaje',
            ),
        ]

    def __str__(self):
        return self.nombre


class AsignacionBeca(models.Model):
    """Beca otorgada a un estudiante para una gestión; una vigente a la vez."""

    class Estado(models.TextChoices):
        VIGENTE = 'VIGENTE', 'Vigente'
        REVOCADA = 'REVOCADA', 'Revocada'

    beca = models.ForeignKey(Beca, on_delete=models.PROTECT, related_name='asignaciones')
    estudiante = models.ForeignKey(
        'estudiantes.Estudiante', on_delete=models.PROTECT, related_name='becas_asignadas',
    )
    calendario_academico = models.ForeignKey(
        'calendario.CalendarioAcademico', on_delete=models.PROTECT, related_name='becas_asignadas',
    )
    motivo = models.TextField()
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.VIGENTE)
    asignado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='becas_otorgadas',
    )
    motivo_revocacion = models.TextField(blank=True)
    revocado_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'finanzas_asignacion_beca'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['estudiante', 'calendario_academico'], condition=Q(estado='VIGENTE'),
                name='uq_beca_vigente_estudiante_gestion',
            ),
            models.CheckConstraint(
                condition=~Q(estado='REVOCADA') | Q(revocado_at__isnull=False),
                name='ck_beca_revocada_fecha',
            ),
        ]

    def __str__(self):
        return f'{self.beca} -> {self.estudiante}'


class ObligacionPago(models.Model):
    """Cuota que un estudiante debe pagar (HU-23), base de pagos y morosidad."""

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        PAGADA = 'PAGADA', 'Pagada'
        ANULADA = 'ANULADA', 'Anulada'

    estudiante = models.ForeignKey(
        'estudiantes.Estudiante', on_delete=models.PROTECT, related_name='obligaciones_pago',
    )
    cuota = models.ForeignKey(CuotaPlan, on_delete=models.PROTECT, related_name='obligaciones')
    asignacion_beca = models.ForeignKey(
        AsignacionBeca, on_delete=models.SET_NULL, null=True, blank=True, related_name='obligaciones',
    )
    monto_original = models.DecimalField(max_digits=12, decimal_places=2)
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_final = models.DecimalField(max_digits=12, decimal_places=2)
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fecha_vencimiento = models.DateField()
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo_anulacion = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'finanzas_obligacion_pago'
        ordering = ['fecha_vencimiento', 'estudiante_id']
        constraints = [
            models.UniqueConstraint(fields=['estudiante', 'cuota'], name='uq_obligacion_estudiante_cuota'),
            models.CheckConstraint(
                condition=Q(descuento__gte=0, descuento__lte=F('monto_original')),
                name='ck_obligacion_descuento',
            ),
            models.CheckConstraint(
                condition=Q(monto_final=F('monto_original') - F('descuento')),
                name='ck_obligacion_monto_final',
            ),
            models.CheckConstraint(
                condition=Q(monto_pagado__gte=0, monto_pagado__lte=F('monto_final')),
                name='ck_obligacion_monto_pagado',
            ),
        ]
        indexes = [
            models.Index(fields=['estado', 'fecha_vencimiento'], name='ix_obligacion_estado_venc'),
        ]

    @property
    def saldo(self):
        return self.monto_final - self.monto_pagado

    @property
    def vencida(self):
        return (
            self.estado == self.Estado.PENDIENTE and self.saldo > 0
            and self.fecha_vencimiento < hoy()
        )

    def __str__(self):
        return f'{self.estudiante} - {self.cuota.concepto}'


class Pago(models.Model):
    """HU-24: recibo de un cobro aplicado a una o más obligaciones."""

    class Metodo(models.TextChoices):
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia bancaria'
        QR = 'QR', 'Pago QR'
        TARJETA = 'TARJETA', 'Tarjeta'

    class Estado(models.TextChoices):
        VALIDO = 'VALIDO', 'Válido'
        ANULADO = 'ANULADO', 'Anulado'

    unidad_educativa = models.ForeignKey(
        'institucion.UnidadEducativa', on_delete=models.PROTECT, related_name='pagos_pension',
    )
    estudiante = models.ForeignKey(
        'estudiantes.Estudiante', on_delete=models.PROTECT, related_name='pagos_pension',
    )
    numero_recibo = models.PositiveIntegerField()
    fecha_pago = models.DateField(default=hoy)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    metodo = models.CharField(max_length=15, choices=Metodo.choices)
    referencia = models.CharField(max_length=100, blank=True)
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.VALIDO)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pagos_pension_registrados',
    )
    motivo_anulacion = models.TextField(blank=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pagos_pension_anulados',
    )
    anulado_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'finanzas_pago'
        ordering = ['-fecha_pago', '-numero_recibo']
        constraints = [
            models.UniqueConstraint(fields=['unidad_educativa', 'numero_recibo'], name='uq_pago_unidad_recibo'),
            models.CheckConstraint(condition=Q(monto__gt=0), name='ck_pago_monto'),
            models.CheckConstraint(
                condition=~Q(estado='ANULADO') | Q(anulado_at__isnull=False), name='ck_pago_anulado_fecha',
            ),
        ]
        indexes = [models.Index(fields=['unidad_educativa', 'fecha_pago'], name='ix_pago_unidad_fecha')]

    def __str__(self):
        return f'Recibo {self.numero_recibo} - {self.estudiante}'


class DetallePago(models.Model):
    pago = models.ForeignKey(Pago, on_delete=models.PROTECT, related_name='detalles')
    obligacion = models.ForeignKey(ObligacionPago, on_delete=models.PROTECT, related_name='detalles_pago')
    monto = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'finanzas_detalle_pago'
        constraints = [
            models.UniqueConstraint(fields=['pago', 'obligacion'], name='uq_detalle_pago_obligacion'),
            models.CheckConstraint(condition=Q(monto__gt=0), name='ck_detalle_pago_monto'),
        ]


class SolicitudQR(models.Model):
    """HU-25: cobro por QR de una o más cuotas; se concilia contra la pasarela."""

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de pago'
        PAGADA = 'PAGADA', 'Pagada'
        EXPIRADA = 'EXPIRADA', 'Expirada'
        OBSERVADA = 'OBSERVADA', 'Observada'
        ANULADA = 'ANULADA', 'Anulada'

    unidad_educativa = models.ForeignKey(
        'institucion.UnidadEducativa', on_delete=models.PROTECT, related_name='solicitudes_qr',
    )
    estudiante = models.ForeignKey(
        'estudiantes.Estudiante', on_delete=models.PROTECT, related_name='solicitudes_qr',
    )
    obligaciones = models.ManyToManyField(ObligacionPago, related_name='solicitudes_qr')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    qr_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    qr_url = models.CharField(max_length=2048, blank=True)
    expira_at = models.DateTimeField()
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    pago = models.OneToOneField(
        Pago, on_delete=models.PROTECT, null=True, blank=True, related_name='solicitud_qr',
    )
    monto_reportado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    observacion = models.TextField(blank=True)
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_qr_creadas',
    )
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_qr_resueltas',
    )
    verificado_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'finanzas_solicitud_qr'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name='ck_solicitud_qr_monto'),
            models.CheckConstraint(
                condition=~Q(estado='PAGADA') | Q(pago__isnull=False), name='ck_solicitud_qr_pagada_con_pago',
            ),
        ]
        indexes = [models.Index(fields=['unidad_educativa', 'estado'], name='ix_solicitud_qr_unidad_estado')]

    def __str__(self):
        return f'QR {self.pk} - {self.estudiante}'


class RecordatorioPago(models.Model):
    """HU-28: registro de recordatorios enviados, para no repetirlos en el mismo día."""

    class Tipo(models.TextChoices):
        VENCIDAS = 'VENCIDAS', 'Cuotas vencidas'
        POR_VENCER = 'POR_VENCER', 'Cuotas por vencer'

    estudiante = models.ForeignKey(
        'estudiantes.Estudiante', on_delete=models.CASCADE, related_name='recordatorios_pago',
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    fecha = models.DateField()
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'finanzas_recordatorio_pago'
        ordering = ['-fecha', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['estudiante', 'tipo', 'fecha'], name='uq_recordatorio_pago_dia'),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.estudiante} ({self.fecha})'

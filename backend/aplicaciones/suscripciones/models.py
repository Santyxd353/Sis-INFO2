from django.db import models
from django.utils import timezone


DIAS_PERIODICIDAD = {
    'MENSUAL': 30,
    'TRIMESTRAL': 90,
    'SEMESTRAL': 180,
    'ANUAL': 365,
}


class Plan(models.Model):
    """Plan comercial de la plataforma SaaS (catálogo global)."""

    class Periodicidad(models.TextChoices):
        MENSUAL = 'MENSUAL', 'Mensual'
        TRIMESTRAL = 'TRIMESTRAL', 'Trimestral'
        SEMESTRAL = 'SEMESTRAL', 'Semestral'
        ANUAL = 'ANUAL', 'Anual'

    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    moneda = models.CharField(max_length=3, default='BOB')
    periodicidad = models.CharField(max_length=20, choices=Periodicidad.choices)
    modulos_habilitados = models.JSONField(default=list, blank=True)
    # 0 = sin límite
    limite_usuarios = models.PositiveIntegerField(default=0)
    limite_unidades = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.ACTIVO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    eliminado_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'suscripciones_plan'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['estado'], name='ix_plan_estado'),
        ]

    def __str__(self):
        return self.nombre

    @property
    def dias_vigencia(self):
        return DIAS_PERIODICIDAD.get(self.periodicidad, 30)

    def desactivar(self):
        self.estado = self.Estado.INACTIVO
        self.eliminado_at = timezone.now()
        self.save(update_fields=['estado', 'eliminado_at', 'updated_at'])


class MetodoPago(models.Model):
    """Canal de cobro habilitado por la plataforma.

    El código está deliberadamente limitado a los mecanismos que el sistema
    sabe procesar. Así se puede activar o desactivar un canal sin aceptar un
    método arbitrario desde la interfaz pública.
    """

    class Codigo(models.TextChoices):
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia bancaria'
        TARJETA = 'TARJETA', 'Tarjeta de crédito o débito'
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        PASARELA = 'PASARELA', 'Pasarela de pago (modo prueba)'
        STRIPE = 'STRIPE', 'Stripe Checkout'
        QR_SIMULADO = 'QR_SIMULADO', 'QR simulado'

    codigo = models.CharField(max_length=20, choices=Codigo.choices, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)
    banco = models.CharField(max_length=120, blank=True)
    titular = models.CharField(max_length=150, blank=True)
    numero_cuenta = models.CharField(max_length=80, blank=True)
    tipo_cuenta = models.CharField(max_length=40, blank=True)
    moneda_cuenta = models.CharField(max_length=3, blank=True)
    instrucciones = models.TextField(blank=True)
    qr_imagen = models.ImageField(upload_to='suscripciones/qr/plataforma/', null=True, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suscripciones_metodo_pago'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class MetodoPagoColegio(models.Model):
    """Configuración de cobro propia de un colegio para un canal habilitado."""
    colegio = models.ForeignKey('institucion.Colegio', on_delete=models.CASCADE, related_name='metodos_pago')
    metodo = models.ForeignKey(MetodoPago, on_delete=models.PROTECT, related_name='configuraciones_colegio')
    nombre_visible = models.CharField(max_length=100, blank=True)
    banco = models.CharField(max_length=120, blank=True)
    titular = models.CharField(max_length=150, blank=True)
    numero_cuenta = models.CharField(max_length=80, blank=True)
    tipo_cuenta = models.CharField(max_length=40, blank=True)
    moneda_cuenta = models.CharField(max_length=3, blank=True)
    instrucciones = models.TextField(blank=True)
    qr_imagen = models.ImageField(upload_to='suscripciones/qr/colegios/', null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suscripciones_metodo_pago_colegio'
        constraints = [models.UniqueConstraint(fields=['colegio', 'metodo'], name='uq_metodo_pago_colegio')]
        ordering = ['metodo__nombre']


class Suscripcion(models.Model):
    """Vigencia de suscripción de un colegio a un plan.

    Cada fila conserva un snapshot de precio, periodicidad, módulos y límites
    al momento de contratar, de modo que cambios posteriores del Plan no
    alteran el historial contratado. Los pagos cuelgan de la vigencia.
    """

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de pago'
        ACTIVA = 'ACTIVA', 'Activa'
        VENCIDA = 'VENCIDA', 'Vencida'
        SUSPENDIDA = 'SUSPENDIDA', 'Suspendida'
        CANCELADA = 'CANCELADA', 'Cancelada'

    colegio = models.ForeignKey(
        'institucion.Colegio',
        on_delete=models.PROTECT,
        related_name='suscripciones',
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name='suscripciones',
    )
    precio_periodico = models.DecimalField(max_digits=10, decimal_places=2)
    moneda = models.CharField(max_length=3, default='BOB')
    periodicidad = models.CharField(max_length=20, choices=Plan.Periodicidad.choices)
    modulos_habilitados = models.JSONField(default=list, blank=True)
    limite_usuarios = models.PositiveIntegerField(default=0)
    limite_unidades = models.PositiveIntegerField(default=0)
    fecha_inicio = models.DateField()
    fecha_vencimiento = models.DateField()
    estado = models.CharField(
        max_length=15, choices=Estado.choices, default=Estado.PENDIENTE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suscripciones_suscripcion'
        ordering = ['-fecha_inicio', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fecha_vencimiento__gte=models.F('fecha_inicio')),
                name='ck_suscripcion_vigencia',
            ),
        ]
        indexes = [
            models.Index(fields=['colegio', 'estado'], name='ix_suscripcion_colegio_estado'),
            models.Index(fields=['estado', 'fecha_vencimiento'], name='ix_suscripcion_estado_venc'),
        ]

    def __str__(self):
        return f'{self.colegio} → {self.plan} ({self.get_estado_display()})'

    @property
    def dias_vigencia(self):
        return DIAS_PERIODICIDAD.get(self.periodicidad, 30)

    @property
    def vigente(self):
        from django.utils import timezone as tz
        return self.estado == self.Estado.ACTIVA and self.fecha_inicio <= tz.localdate() <= self.fecha_vencimiento


class Pago(models.Model):
    """Registro de pago de una suscripción. Solo un pago validado activa o renueva."""

    class Metodo(models.TextChoices):
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia bancaria'
        TARJETA = 'TARJETA', 'Tarjeta'
        EFECTIVO = 'EFECTIVO', 'Efectivo'
        PASARELA = 'PASARELA', 'Pasarela de pago (modo prueba)'
        STRIPE = 'STRIPE', 'Stripe Checkout'
        QR_SIMULADO = 'QR_SIMULADO', 'QR simulado'

    class Resultado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de validación'
        VALIDADO = 'VALIDADO', 'Validado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'

    suscripcion = models.ForeignKey(
        Suscripcion, on_delete=models.PROTECT, related_name='pagos',
    )
    metodo = models.CharField(max_length=20, choices=Metodo.choices)
    referencia = models.CharField(max_length=120)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    moneda = models.CharField(max_length=3, default='BOB')
    fecha = models.DateField()
    resultado = models.CharField(
        max_length=15, choices=Resultado.choices, default=Resultado.PENDIENTE,
    )
    observacion = models.CharField(max_length=255, blank=True)
    validado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pagos_validados',
    )
    validado_at = models.DateTimeField(null=True, blank=True)
    qr_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    qr_url = models.URLField(max_length=2048, blank=True)
    qr_expira_at = models.DateTimeField(null=True, blank=True)
    stripe_session_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suscripciones_pago'
        ordering = ['-fecha', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['suscripcion'],
                condition=models.Q(metodo='STRIPE', resultado='PENDIENTE'),
                name='uq_pago_stripe_pendiente',
            ),
        ]
        indexes = [
            models.Index(fields=['fecha'], name='ix_pago_fecha'),
        ]

    def __str__(self):
        return f'Pago {self.pk} {self.monto} {self.moneda} ({self.get_resultado_display()})'

from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.conf import settings
from django.apps import AppConfig
import uuid

class MultiToken(models.Model):
    key = models.CharField(max_length=40, primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='multi_tokens',
        on_delete=models.CASCADE
    )
    created = models.DateTimeField(auto_now_add=True)
    device_name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.device_name or 'sin nombre'}"

class Rol(models.Model):
    class Categoria(models.TextChoices):
        BASE = 'BASE', 'Base'
        FUNCIONAL = 'FUNCIONAL', 'Funcional'

    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    # HU-SE02: roles del sistema (colegio=None) vs roles personalizados por colegio (tenant).
    colegio = models.ForeignKey(
        'institucion.Colegio',
        on_delete=models.PROTECT,
        related_name='roles',
        null=True,
        blank=True,
    )
    activo = models.BooleanField(default=True)
    categoria = models.CharField(
        max_length=12,
        choices=Categoria.choices,
        default=Categoria.FUNCIONAL,
    )
    unidad_educativa = models.ForeignKey(
        'institucion.UnidadEducativa',
        on_delete=models.PROTECT,
        related_name='roles',
        null=True,
        blank=True,
    )
    puesto = models.ForeignKey(
        'usuarios.Puesto',
        on_delete=models.PROTECT,
        related_name='roles_institucionales',
        null=True,
        blank=True,
    )

    class Meta:
        app_label = 'usuarios'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
        db_table = 'rol'
        constraints = [
            models.UniqueConstraint(
                fields=['nombre'],
                condition=models.Q(colegio__isnull=True),
                name='uq_rol_sistema_nombre',
            ),
            models.UniqueConstraint(
                fields=['colegio', 'nombre'],
                condition=models.Q(colegio__isnull=False),
                name='uq_rol_colegio_nombre',
            ),
        ]

    @property
    def es_sistema(self):
        return self.colegio_id is None

    @property
    def alcance(self):
        if self.colegio_id is None and self.unidad_educativa_id is None:
            return 'SISTEMA'
        if self.unidad_educativa_id is not None:
            return 'UNIDAD'
        return 'COLEGIO'

    def __str__(self):
        return self.nombre if self.colegio_id is None else f'{self.nombre} ({self.colegio})'
    

class UsuarioManager(BaseUserManager):
    def create_user(self, ci, email, nombre, apellido, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        if not ci:
            raise ValueError('El CI es obligatorio')
        
        email = self.normalize_email(email)
        user = self.model(
            ci=ci,
            email=email,
            nombre=nombre,
            apellido=apellido,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, ci, email, nombre, apellido, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('debe_cambiar_password', False)
        
        # Obtener o crear rol de SuperAdmin
        rol, _ = Rol.objects.get_or_create(nombre='SuperAdmin')
        extra_fields.setdefault('rol', rol)
        
        user = self.create_user(ci, email, nombre, apellido, password, **extra_fields)
        # Asegurar que exista el perfil SuperAdmin asociado al usuario.
        SuperAdmin.objects.get_or_create(usuario=user)
        return user
    
class UsuariosConfig(AppConfig):
    name = 'aplicaciones.usuarios'
    label = 'usuarios'

class Usuario(AbstractBaseUser, PermissionsMixin):
    ci = models.CharField(max_length=20, unique=True)
    foto = models.ImageField(upload_to='usuarios/fotos/', blank=True, null=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)  # Reemplazo de edad
    username = models.CharField(max_length=50, unique=True)
    estado = models.BooleanField(default=True)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT)
    # HU-SE02: roles personalizados adicionales del colegio (además del rol base).
    roles_extras = models.ManyToManyField(
        Rol, blank=True, related_name='usuarios_extras', verbose_name='Roles adicionales',
    )
    unidad = models.ForeignKey(
        'institucion.UnidadEducativa',
        on_delete=models.PROTECT,
        related_name='usuarios',
        null=True,
        blank=True,
    )
    telefono = models.CharField(max_length=20, blank=True, null=True)
    password_reset_pin = models.CharField(max_length=6, blank=True, null=True)
    debe_cambiar_password = models.BooleanField(default=True)

    SEXO_MASCULINO = 'M'
    SEXO_FEMENINO = 'F'
    SEXO_CHOICES = [
        (SEXO_MASCULINO, 'Masculino'),
        (SEXO_FEMENINO, 'Femenino'),
    ]
    sexo = models.CharField(
        max_length=1,            # CORRECCIÓN: max_length en lugar de max_lenght
        choices=SEXO_CHOICES,    # sólo ‘M’ o ‘F’
        default=SEXO_MASCULINO,  # opcional: valor por defecto
    )
    
    # Campos requeridos para el modelo de usuario personalizado
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['ci', 'email', 'nombre', 'apellido', 'fecha_nacimiento']  # Actualización de campos requeridos

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        db_table = 'usuario'

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

    def get_full_name(self):
        return f"{self.nombre} {self.apellido}"

    def get_short_name(self):
        return self.nombre

class Notificacion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    titulo = models.CharField(max_length=100)
    mensaje = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)
    tipo = models.CharField(max_length=50)

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        db_table = 'notificacion'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.titulo} - {self.usuario}"


class RegistroInstitucional(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='registro_institucional')
    colegio = models.OneToOneField('institucion.Colegio', on_delete=models.PROTECT)
    plan_seleccionado = models.ForeignKey('suscripciones.Plan', on_delete=models.SET_NULL, null=True, blank=True)
    condiciones_aceptadas_at = models.DateTimeField()
    verificado_at = models.DateTimeField(null=True, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)

class SuperAdmin(models.Model):
    usuario = models.OneToOneField(
        Usuario, 
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='superadmin'
    )
    

    class Meta:
        verbose_name = 'Super Administrador'
        verbose_name_plural = 'Super Administraadores'
        db_table = 'superadmin'

    def __str__(self):
        return str(self.usuario)
    
class Puesto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class Accion(models.Model):
    # Acciones CRUD
    nombre = models.CharField(max_length=20, unique=True)  # Ej: 'add', 'view', 'change', 'delete'

    class Meta: 
        verbose_name = 'Acción'
        verbose_name_plural = 'Acciones'
        db_table = 'accion'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
    

    
class ModeloPermitido(models.Model):
    # Aquí puedes definir a qué modelo afecta el permiso
    nombre = models.CharField(max_length=50, unique=True)  # Ej: 'profesor', 'estudiante', 'curso'

    class Meta:
        verbose_name = 'Modelo Permitido'
        verbose_name_plural = 'Modelos Permitidos'
        db_table = 'modelo_permitido'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
    
class PermisoRol(models.Model):
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='permisos')
    modelo = models.ForeignKey(ModeloPermitido, on_delete=models.CASCADE)
    accion = models.ForeignKey(Accion, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('rol', 'modelo', 'accion')
        db_table = 'permiso_rol'

    def __str__(self):
        return f"{self.rol} puede {self.accion} en {self.modelo}"
    
class PermisoPuesto(models.Model):
    puesto = models.ForeignKey(Puesto, on_delete=models.CASCADE, related_name='permisos')
    modelo = models.ForeignKey(ModeloPermitido, on_delete=models.CASCADE)
    accion = models.ForeignKey(Accion, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('puesto', 'modelo', 'accion')

    def __str__(self):
        return f"{self.puesto} puede {self.accion} en {self.modelo}"

class PermisoComponente(models.Model):
    """HU-SE02: visibilidad/edición de componentes de interfaz por rol.

    Los permisos de interfaz controlan únicamente la UI (menús, formularios,
    campos, botones); la seguridad del backend se valida por separado con los
    permisos funcionales. Un componente sin configuración se considera visible
    por defecto y no editable.
    """

    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='componentes')
    componente = models.CharField(max_length=100)
    visible = models.BooleanField(default=True)
    editable = models.BooleanField(default=False)

    class Meta:
        unique_together = ('rol', 'componente')
        db_table = 'permiso_componente'
        ordering = ['componente']

    def __str__(self):
        return f"{self.rol}: {self.componente}"

class Admin(models.Model):
    usuario = models.OneToOneField(
        Usuario, 
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='admin'
    )
    puesto = models.ForeignKey(
        Puesto, 
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    unidad = models.ForeignKey(
        'institucion.UnidadEducativa',
        on_delete=models.PROTECT,
        related_name="admins",
        null=True,
        blank=True
    )
    colegio = models.ForeignKey(
        'institucion.Colegio',
        on_delete=models.PROTECT,
        related_name='administradores',
        null=True,
        blank=True,
    )
    estado = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Administrador'
        verbose_name_plural = 'Administradores'
        db_table = 'admin'

    def __str__(self):
        return f"{self.usuario} → {self.unidad}"
    



# Create your models here.
from django.db import models
from django.conf import settings

class Bitacora(models.Model):
    ACCIONES = [
        ('crear', 'Crear'),
        ('editar', 'Editar'),
        ('eliminar', 'Eliminar'),
        ('listar', 'Listar'),
        ('otro', 'Otro'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Usuario relacionado'
    )
    hora_entrada = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Hora de entrada'
    )
    hora_salida = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Hora de salida'
    )
    ip = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        verbose_name="Dirección IP"
    )
    tabla_afectada = models.CharField(
        max_length=100,
        verbose_name='Tabla afectada',
        blank=True,
        null=True
    )
    accion = models.CharField(
        max_length=10,
        choices=ACCIONES,
        verbose_name='Acción realizada',
        default='otro'  # Valor predeterminado
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción de la acción',
    )
    fecha = models.DateTimeField(
        verbose_name='Fecha de registro',
        default=timezone.now
    )

    class Meta:
        verbose_name = 'Bitácora de sesión'
        verbose_name_plural = 'Bitácoras de sesión'
        db_table = 'bitacora_sesion'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.usuario} realizó {self.accion} el {self.fecha:%Y-%m-%d %H:%M:%S}"


class EventoAuditoria(models.Model):
    class Ambito(models.TextChoices):
        GLOBAL = 'GLOBAL', 'Global'
        COLEGIO = 'COLEGIO', 'Colegio'
        UNIDAD = 'UNIDAD', 'Unidad'

    ambito = models.CharField(max_length=20, choices=Ambito.choices)
    colegio = models.ForeignKey(
        'institucion.Colegio', on_delete=models.RESTRICT,
        related_name='eventos_auditoria', null=True, blank=True,
    )
    unidad_educativa = models.ForeignKey(
        'institucion.UnidadEducativa', on_delete=models.RESTRICT,
        related_name='eventos_auditoria', null=True, blank=True,
    )
    # Identificador histórico: no es una llave foránea para que la eliminación
    # de una cuenta no modifique un evento ya registrado.
    usuario = models.BigIntegerField(null=True, blank=True)
    actor_snapshot = models.CharField(max_length=200, null=True, blank=True)
    accion = models.CharField(max_length=80)
    entidad = models.CharField(max_length=100)
    entidad_id = models.CharField(max_length=80, null=True, blank=True)
    cambios_sanitizados = models.JSONField(null=True, blank=True)
    ip_hash = models.CharField(max_length=128, null=True, blank=True)
    correlacion = models.UUIDField(default=uuid.uuid4, editable=False)
    fecha_cliente = models.DateTimeField(null=True, blank=True)
    zona_cliente = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auditoria_evento'
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(ambito='GLOBAL', colegio__isnull=True, unidad_educativa__isnull=True)
                    | models.Q(ambito='COLEGIO', colegio__isnull=False, unidad_educativa__isnull=True)
                    | models.Q(ambito='UNIDAD', colegio__isnull=False, unidad_educativa__isnull=False)
                ),
                name='ck_auditoria_ambito_relaciones',
            ),
        ]
        indexes = [
            models.Index(fields=['colegio', 'created_at'], name='ix_auditoria_colegio_fecha'),
            models.Index(fields=['unidad_educativa', 'created_at'], name='ix_auditoria_unidad_fecha'),
            models.Index(fields=['usuario', 'created_at'], name='ix_auditoria_usuario_fecha'),
            models.Index(fields=['entidad', 'entidad_id'], name='ix_auditoria_entidad'),
            models.Index(fields=['correlacion'], name='ix_auditoria_correlacion'),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Los eventos de auditoría son inmutables.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Los eventos de auditoría no se pueden eliminar.')

class DispositivoNotificacion(models.Model):
    """HU-movil Fase 3: token de push (Expo) de un dispositivo del usuario."""

    class Plataforma(models.TextChoices):
        ANDROID = 'ANDROID', 'Android'
        IOS = 'IOS', 'iOS'
        WEB = 'WEB', 'Web'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='dispositivos_notificacion',
    )
    token = models.CharField(max_length=255, unique=True)
    plataforma = models.CharField(max_length=10, choices=Plataforma.choices)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dispositivo de notificación'
        verbose_name_plural = 'Dispositivos de notificación'
        db_table = 'usuario_dispositivo_notificacion'
        indexes = [
            models.Index(fields=['usuario', 'activo'], name='ix_dispositivo_usuario_activo'),
        ]

    def __str__(self):
        return f'{self.usuario} - {self.plataforma}'

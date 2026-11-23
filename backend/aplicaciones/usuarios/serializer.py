from rest_framework import serializers
from django.db import transaction
from .models import Usuario, Rol, Notificacion, Bitacora, SuperAdmin, Puesto, Admin, Accion, ModeloPermitido, PermisoPuesto, PermisoRol, PermisoComponente
from django.contrib.auth.hashers import make_password
from django.apps import apps as models
from aplicaciones.institucion.models import UnidadEducativa, Colegio
from aplicaciones.usuarios.tenancy import normalizar_nombre
from aplicaciones.institucion.serializers import ColegioSerializer
from aplicaciones.institucion.serializers import UnidadEducativaSerializer
from aplicaciones.academico.models import Curso

class RolSerializer(serializers.ModelSerializer):
    """HU-SE02: roles del sistema (colegio=None) y personalizados por colegio."""

    colegio_id = serializers.PrimaryKeyRelatedField(
        queryset=Colegio.objects.all(), source='colegio',
        required=False, allow_null=True,
    )
    unidad_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadEducativa.objects.all(), source='unidad_educativa',
        required=False, allow_null=True,
    )
    puesto_id = serializers.PrimaryKeyRelatedField(
        queryset=Puesto.objects.all(), source='puesto', required=False, allow_null=True,
    )
    puesto = serializers.SerializerMethodField()
    categoria = serializers.SerializerMethodField()
    alcance = serializers.SerializerMethodField()
    permisos = serializers.SerializerMethodField()
    componentes = serializers.SerializerMethodField()

    class Meta:
        model = Rol
        fields = [
            'id', 'nombre', 'descripcion', 'colegio_id', 'activo',
            'unidad_id', 'puesto_id', 'puesto', 'categoria', 'alcance', 'permisos', 'componentes',
        ]
        read_only_fields = ['id']
        # DRF 3.18 deriva UniqueTogetherValidator de nuestras UniqueConstraint
        # condicionales y fuerza colegio_id como requerido; la unicidad por
        # alcance (sistema/colegio) se valida en validate().
        validators = []
        extra_kwargs = {
            'nombre': {'required': True, 'allow_blank': False},
            'descripcion': {'required': False},
        }

    def get_categoria(self, obj):
        return getattr(obj.categoria, 'value', obj.categoria)

    def get_alcance(self, obj):
        return obj.alcance

    def get_puesto(self, obj):
        return {'id': obj.puesto_id, 'nombre': obj.puesto.nombre} if obj.puesto_id else None

    def get_permisos(self, obj):
        return [
            {'modelo': permiso.modelo.nombre, 'accion': permiso.accion.nombre}
            for permiso in obj.permisos.select_related('modelo', 'accion').order_by(
                'modelo__nombre', 'accion__nombre',
            )
        ]

    def get_componentes(self, obj):
        return [
            {'componente': componente.componente, 'visible': componente.visible,
             'editable': componente.editable}
            for componente in obj.componentes.all()
        ]

    def validate(self, attrs):
        from aplicaciones.usuarios.privilegios import es_superadmin

        nombre = attrs.get('nombre', getattr(self.instance, 'nombre', None))
        colegio = attrs.get('colegio', getattr(self.instance, 'colegio', None))
        unidad = attrs.get('unidad_educativa', getattr(self.instance, 'unidad_educativa', None))
        puesto = attrs.get('puesto', getattr(self.instance, 'puesto', None))
        categoria = getattr(self.instance, 'categoria', Rol.Categoria.FUNCIONAL)
        if self.instance is None and categoria == Rol.Categoria.FUNCIONAL:
            # La categoría se deriva del contrato de creación, nunca del cliente.
            categoria = Rol.Categoria.FUNCIONAL
        if unidad is not None:
            if colegio is None:
                raise serializers.ValidationError({'unidad_id': 'Una unidad requiere un colegio.'})
            if unidad.colegio_id != colegio.pk:
                raise serializers.ValidationError({'unidad_id': 'La unidad no pertenece al colegio seleccionado.'})
        if puesto is not None and categoria == Rol.Categoria.BASE:
            raise serializers.ValidationError({'puesto_id': 'Los roles base no se asocian a puestos institucionales.'})
        if puesto is not None and colegio is None:
            raise serializers.ValidationError({'colegio_id': 'Una configuración de puesto requiere un colegio.'})
        if categoria == Rol.Categoria.BASE:
            if colegio is not None or unidad is not None:
                raise serializers.ValidationError({'categoria': 'Los roles base solo pueden ser globales.'})
            if self.instance and (
                'nombre' in attrs or 'colegio' in attrs or 'unidad_educativa' in attrs
            ):
                raise serializers.ValidationError({'nombre': 'Los roles base no pueden modificarse.'})
        if nombre and colegio is not None:
            from .tenancy import normalizar_nombre
            if normalizar_nombre(nombre) in {'superadmin', 'super admin'}:
                raise serializers.ValidationError({'nombre': 'Este nombre está reservado para la administración de la plataforma.'})
        if nombre:
            coincidencias = Rol.objects.filter(nombre__iexact=nombre)
            if colegio is None:
                coincidencias = coincidencias.filter(colegio__isnull=True)
            else:
                coincidencias = coincidencias.filter(colegio_id=colegio.pk)
            if self.instance:
                coincidencias = coincidencias.exclude(pk=self.instance.pk)
            if coincidencias.exists():
                ambito = 'este colegio' if colegio else 'el sistema'
                raise serializers.ValidationError({
                    'nombre': f'Ya existe un rol con este nombre en {ambito}.',
                })
        # Solo SuperAdmin crea roles de sistema (sin colegio). Un admin no
        # puede solicitarlo explícitamente con colegio_id nulo; si no envía
        # colegio, la vista lo forzará al de su propio tenant.
        request = self.context.get('request')
        solicitante = getattr(request, 'user', None)
        if solicitante and hasattr(solicitante, 'admin') and nombre:
            from .tenancy import normalizar_nombre
            if normalizar_nombre(nombre) in {'superadmin', 'super admin', 'director', 'admin director'}:
                raise serializers.ValidationError({
                    'nombre': 'Ese nombre está reservado para la jerarquía administrativa.'
                })
        explicito_sistema = (
            self.instance is None and request is not None
            and 'colegio_id' in getattr(request, 'data', {})
            and request.data.get('colegio_id') is None
        )
        if explicito_sistema and solicitante and not es_superadmin(solicitante):
            raise serializers.ValidationError({
                'colegio_id': 'Solo el Superadministrador puede crear roles de sistema.',
            })
        return attrs

class UsuarioSerializer(serializers.ModelSerializer):
    rol = RolSerializer(read_only=True)
    rol_id = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.all(),
        source='rol',
        write_only=True
    )
    unidad = UnidadEducativaSerializer(read_only=True)
    unidad_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadEducativa.objects.all(),
        source='unidad',
        write_only=True,
        required=False,
        allow_null=True,
    )
    colegio = serializers.SerializerMethodField()
    colegio_id = serializers.PrimaryKeyRelatedField(
        queryset=Colegio.objects.all(), write_only=True, required=False, allow_null=True,
    )
    puesto_id = serializers.PrimaryKeyRelatedField(
        queryset=Puesto.objects.all(), write_only=True, required=False, allow_null=True,
    )
    curso_ids = serializers.PrimaryKeyRelatedField(
        queryset=Curso.objects.all(), many=True, write_only=True, required=False,
    )
    curso_estudiante_id = serializers.PrimaryKeyRelatedField(
        queryset=Curso.objects.all(), write_only=True, required=False, allow_null=True,
    )
    rude = serializers.CharField(write_only=True, required=False, allow_blank=True)
    parentesco = serializers.ChoiceField(
        choices=('PAD', 'MAD', 'TUT', 'HER', 'OTR'),
        write_only=True,
        required=False,
        default='OTR',
    )
    perfil = serializers.SerializerMethodField()
    alcance = serializers.SerializerMethodField()
    permisos_efectivos = serializers.SerializerMethodField()
    # HU-SE02: roles personalizados adicionales, permisos de interfaz y categoría.
    roles_extras = serializers.SerializerMethodField()
    roles_extra_ids = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.all(), many=True, write_only=True,
        source='roles_extras', required=False,
    )
    permisos_ui = serializers.SerializerMethodField()
    categoria = serializers.SerializerMethodField()
    
    class Meta:
        model = Usuario
        fields = [
            'id', 'ci', 'username', 'email', 'nombre', 'apellido',
             'foto', 'telefono', 'fecha_nacimiento', 'sexo', 'rol_id', 'rol',
            'unidad_id', 'unidad', 'colegio_id', 'colegio', 'puesto_id', 'curso_ids', 'curso_estudiante_id',
            'rude', 'parentesco', 'perfil', 'alcance', 'permisos_efectivos',
            'roles_extras', 'roles_extra_ids', 'permisos_ui', 'categoria',
            'is_active', 'debe_cambiar_password',
            'date_joined','password'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'is_active': {'read_only': True},
            'date_joined': {'read_only': True}
        }
    
    def validate(self, attrs):
        rol = attrs.get('rol', getattr(self.instance, 'rol', None))
        unidad = attrs.get('unidad', getattr(self.instance, 'unidad', None))
        admin_actual = getattr(self.instance, 'admin', None) if self.instance else None
        if admin_actual and admin_actual.unidad_id != self.instance.unidad_id:
            raise serializers.ValidationError({'unidad_id': 'El perfil administrativo y el usuario tienen unidades divergentes.'})
        puesto = attrs.get('puesto_id', getattr(admin_actual, 'puesto', None))
        colegio = attrs.get('colegio_id', getattr(admin_actual, 'colegio', None))
        if admin_actual and 'puesto_id' in attrs and attrs['puesto_id'] is None:
            raise serializers.ValidationError({'puesto_id': 'El puesto administrativo no puede ser nulo.'})
        rol_nombre = normalizar_nombre(rol.nombre) if rol else ''
        puesto_nombre = normalizar_nombre(puesto.nombre) if puesto else ''
        roles_base = {'superadmin', 'admin', 'profesor', 'tutor', 'estudiante'}
        if rol_nombre not in roles_base:
            raise serializers.ValidationError({
                'rol_id': 'Use uno de los roles base: Admin, Profesor, Tutor o Estudiante.'
            })
        if rol and rol.colegio_id is not None:
            raise serializers.ValidationError({'rol_id': 'El rol principal debe ser un rol base del sistema.'})
        if self.instance and rol and rol.pk != self.instance.rol_id:
            raise serializers.ValidationError({
                'rol_id': 'El rol no puede cambiarse desde la edición general del usuario.'
            })
        if not self.instance and rol_nombre == 'superadmin':
            raise serializers.ValidationError({
                'rol_id': 'Los superusuarios se crean únicamente desde la administración del servidor.'
            })
        if rol_nombre != 'superadmin' and not unidad and not (
            rol_nombre == 'admin' and puesto_nombre in {'director', 'tesoreria'}
        ):
            raise serializers.ValidationError({'unidad_id': 'La unidad educativa es obligatoria.'})
        if rol_nombre == 'admin' and puesto_nombre in {'director', 'secretaria', 'tesoreria'}:
            if not colegio:
                raise serializers.ValidationError({'colegio_id': 'El colegio es obligatorio.'})
            if colegio.estado != Colegio.Estado.ACTIVO:
                raise serializers.ValidationError({'colegio_id': 'El colegio seleccionado no está activo.'})
            if puesto_nombre == 'secretaria' and not unidad:
                raise serializers.ValidationError({'unidad_id': 'La unidad educativa es obligatoria para Secretaría.'})
            if unidad and unidad.colegio_id != colegio.pk:
                raise serializers.ValidationError({
                    'unidad_id': 'La unidad educativa debe pertenecer al colegio seleccionado.'
                })
        if rol_nombre == 'admin' and unidad and colegio and unidad.colegio_id != colegio.pk:
            raise serializers.ValidationError({'unidad_id': 'La unidad educativa debe pertenecer al colegio seleccionado.'})
        request = self.context.get('request')
        solicitante = getattr(request, 'user', None)
        if solicitante and hasattr(solicitante, 'admin'):
            from aplicaciones.usuarios.tenancy import resolver_alcance, validar_unidad
            alcance = resolver_alcance(solicitante)
            if colegio and alcance['colegio_id'] != colegio.pk:
                raise serializers.ValidationError({'colegio_id': 'El colegio está fuera de su alcance.'})
            if unidad:
                try:
                    validar_unidad(solicitante, unidad)
                except serializers.ValidationError:
                    raise
                except Exception as exc:
                    raise serializers.ValidationError({'unidad_id': str(exc.detail)})
            puesto_solicitante = normalizar_nombre(getattr(solicitante.admin.puesto, 'nombre', ''))
            puesto_destino = attrs.get('puesto_id')
            if rol_nombre == 'admin' and puesto_solicitante != 'director':
                raise serializers.ValidationError({
                    'rol_id': 'Solo Dirección puede registrar personal administrativo.'
                })
            if (
                rol_nombre == 'admin' and puesto_destino
                and normalizar_nombre(puesto_destino.nombre) == 'director'
            ):
                raise serializers.ValidationError({
                    'puesto_id': 'Solo el Super Administrador puede registrar directores.'
                })
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'La contraseña temporal es obligatoria.'})
        if rol_nombre == 'admin' and not attrs.get('puesto_id') and not self.instance:
            raise serializers.ValidationError({'puesto_id': 'Seleccione el puesto administrativo.'})
        if rol_nombre == 'estudiante':
            if not attrs.get('curso_estudiante_id') and not self.instance:
                raise serializers.ValidationError({'curso_estudiante_id': 'Seleccione el curso del estudiante.'})
            if not attrs.get('rude') and not self.instance:
                raise serializers.ValidationError({'rude': 'El RUDE es obligatorio.'})

        cursos = list(attrs.get('curso_ids', []))
        curso_estudiante = attrs.get('curso_estudiante_id')
        for curso in cursos + ([curso_estudiante] if curso_estudiante else []):
            curso_unidad = curso.paralelo.grado.unidad_educativa_id
            if unidad and curso_unidad != unidad.pk:
                raise serializers.ValidationError({
                    'unidad_id': 'Todos los cursos deben pertenecer a la unidad seleccionada.',
                })

        # HU-SE02: los roles adicionales deben ser roles personalizados activos
        # del mismo colegio que el usuario y no pueden delegar privilegios
        # superiores a los del solicitante.
        extras = attrs.get('roles_extras')
        if extras is not None:
            from aplicaciones.usuarios.privilegios import (
                es_superadmin, roles_no_delegables,
            )
            colegio_destino = None
            if unidad is not None and unidad.colegio_id:
                colegio_destino = unidad.colegio_id
            elif colegio is not None:
                colegio_destino = colegio.pk
            elif self.instance is not None and self.instance.unidad_id:
                colegio_destino = self.instance.unidad.colegio_id
            for rol in extras:
                if not rol.activo:
                    raise serializers.ValidationError({
                        'roles_extra_ids': f'El rol "{rol.nombre}" está inactivo.',
                    })
                if rol.categoria != Rol.Categoria.FUNCIONAL:
                    raise serializers.ValidationError({
                        'roles_extra_ids': (
                            f'El rol "{rol.nombre}" es un rol base del sistema; '
                            'asígnelo como rol principal.'
                        ),
                    })
                if not rol.permisos.exists():
                    raise serializers.ValidationError({
                        'roles_extra_ids': f'El rol "{rol.nombre}" no tiene permisos asignados.',
                    })
                if rol.colegio_id is not None and colegio_destino is not None and rol.colegio_id != colegio_destino:
                    raise serializers.ValidationError({
                        'roles_extra_ids': (
                            f'El rol "{rol.nombre}" pertenece a otro colegio.'
                        ),
                    })
                if rol.unidad_educativa_id is not None and rol.unidad_educativa_id != getattr(unidad, 'pk', None):
                    raise serializers.ValidationError({
                        'roles_extra_ids': f'El rol "{rol.nombre}" pertenece a otra unidad educativa.',
                    })
            if solicitante and not es_superadmin(solicitante):
                if roles_no_delegables(solicitante, extras):
                    raise serializers.ValidationError({
                        'roles_extra_ids': (
                            'No puede asignar roles con privilegios superiores '
                            'a los que posee.'
                        ),
                    })
        return attrs

    def get_perfil(self, obj):
        if hasattr(obj, 'admin'):
            return {
                'tipo': 'admin',
                'puesto': PuestoSerializer(obj.admin.puesto).data if obj.admin.puesto else None,
            }
        if hasattr(obj, 'profesor'):
            cursos = obj.profesor.cursos_tutorados.select_related('paralelo__grado').all()
            return {
                'tipo': 'profesor',
                'cursos': [{'id': curso.pk, 'nombre': curso.nombre} for curso in cursos],
            }
        if hasattr(obj, 'estudiante'):
            return {
                'tipo': 'estudiante',
                'rude': obj.estudiante.rude,
                'curso': (
                    {'id': obj.estudiante.curso_id, 'nombre': obj.estudiante.curso.nombre}
                    if obj.estudiante.curso else None
                ),
            }
        if hasattr(obj, 'tutor'):
            return {'tipo': 'tutor', 'parentesco': obj.tutor.parentesco}
        if hasattr(obj, 'superadmin'):
            return {'tipo': 'superadmin'}
        return None

    def get_colegio(self, obj):
        if hasattr(obj, 'admin') and obj.admin.colegio_id:
            return ColegioSerializer(obj.admin.colegio).data
        return None

    def get_alcance(self, obj):
        from aplicaciones.usuarios.tenancy import serializar_alcance
        return serializar_alcance(obj)

    def get_permisos_efectivos(self, obj):
        from aplicaciones.usuarios.privilegios import permisos_funcionales
        permisos = permisos_funcionales(obj)
        if permisos is None:
            return []
        return [
            {'modelo': modelo, 'accion': accion}
            for modelo, accion in sorted(permisos)
        ]

    def get_roles_extras(self, obj):
        return [
            {'id': rol.pk, 'nombre': rol.nombre, 'colegio_id': rol.colegio_id}
            for rol in obj.roles_extras.filter(activo=True).order_by('nombre')
        ]

    def get_permisos_ui(self, obj):
        from aplicaciones.usuarios.privilegios import permisos_ui
        return permisos_ui(obj)

    def get_categoria(self, obj):
        from aplicaciones.usuarios.privilegios import categoria_usuario
        return categoria_usuario(obj)

    def _extraer_perfil(self, validated_data):
        return {
            'puesto': validated_data.pop('puesto_id', None),
            'colegio': validated_data.pop('colegio_id', None),
            'cursos': validated_data.pop('curso_ids', None),
            'curso_estudiante': validated_data.pop('curso_estudiante_id', None),
            'rude': validated_data.pop('rude', ''),
            'parentesco': validated_data.pop('parentesco', 'OTR'),
            'roles_extras': validated_data.pop('roles_extras', None),
        }

    def create(self, validated_data):
        from django.db import transaction
        from aplicaciones.estudiantes.models import Estudiante, Tutor
        from aplicaciones.personal.models import Profesor

        perfil = self._extraer_perfil(validated_data)
        password = validated_data.pop('password')
        rol_nombre = validated_data['rol'].nombre.strip().lower()
        unidad = validated_data.get('unidad')
        roles_extras = perfil.pop('roles_extras', None)
        with transaction.atomic():
            usuario = Usuario.objects.create_user(password=password, **validated_data)
            if roles_extras is not None:
                usuario.roles_extras.set(roles_extras)
            if rol_nombre == 'admin':
                Admin.objects.create(
                    usuario=usuario, puesto=perfil['puesto'], unidad=unidad,
                    colegio=perfil['colegio'], estado=True,
                )
            elif rol_nombre == 'profesor':
                profesor = Profesor.objects.create(usuario=usuario, unidad=unidad, estado=True)
                Curso.objects.filter(
                    pk__in=[curso.pk for curso in (perfil['cursos'] or [])]
                ).update(tutor=profesor)
            elif rol_nombre == 'tutor':
                Tutor.objects.create(usuario=usuario, parentesco=perfil['parentesco'])
            elif rol_nombre == 'estudiante':
                Estudiante.objects.create(
                    usuario=usuario, unidad=unidad, curso=perfil['curso_estudiante'],
                    rude=perfil['rude'], estado=True,
                )
        return usuario

    @transaction.atomic
    def update(self, instance, validated_data):
        from aplicaciones.personal.models import Profesor

        perfil = self._extraer_perfil(validated_data)
        password = validated_data.pop('password', None)
        roles_extras = perfil.pop('roles_extras', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles_extras is not None:
            instance.roles_extras.set(roles_extras)
        rol_nombre = instance.rol.nombre.strip().lower()
        if rol_nombre == 'admin' and hasattr(instance, 'admin'):
            instance.admin.unidad = instance.unidad
            if perfil['puesto'] is not None:
                instance.admin.puesto = perfil['puesto']
            if perfil['colegio'] is not None:
                instance.admin.colegio = perfil['colegio']
            instance.admin.save()
        elif rol_nombre == 'profesor':
            profesor, _ = Profesor.objects.get_or_create(
                usuario=instance, defaults={'unidad': instance.unidad, 'estado': True}
            )
            profesor.unidad = instance.unidad
            profesor.save()
            if perfil['cursos'] is not None:
                Curso.objects.filter(tutor=profesor).update(tutor=None)
                Curso.objects.filter(pk__in=[c.pk for c in perfil['cursos']]).update(tutor=profesor)
        elif rol_nombre == 'estudiante' and hasattr(instance, 'estudiante'):
            instance.estudiante.unidad = instance.unidad
            if perfil['curso_estudiante'] is not None:
                instance.estudiante.curso = perfil['curso_estudiante']
            if perfil['rude']:
                instance.estudiante.rude = perfil['rude']
            instance.estudiante.save()
        elif rol_nombre == 'tutor' and hasattr(instance, 'tutor') and perfil['parentesco']:
            instance.tutor.parentesco = perfil['parentesco']
            instance.tutor.save()
        return instance

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = '__all__'
        read_only_fields = ('fecha', 'usuario')

class BitacoraSerializer(serializers.ModelSerializer):
    # Assign current authenticated user automatically
    usuario = serializers.HiddenField(default=serializers.CurrentUserDefault())
    hora_entrada = serializers.DateTimeField(read_only=True)
    fecha = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Bitacora
        fields = [
            'id',
            'usuario',
            'hora_entrada',
            'hora_salida',
            'ip',
            'tabla_afectada',
            'accion',
            'descripcion',
            'fecha',
        ]
        read_only_fields = ['id']

class SuperAdminSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)

    class Meta:
        model = SuperAdmin
        fields = ['usuario_id', 'usuario']

class PuestoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Puesto
        fields = ['id', 'nombre', 'descripcion']
        read_only_fields = ['id']

class AdminSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)
    usuario_id = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.all(),
        source='usuario',
        write_only=True
    )
    puesto = PuestoSerializer(read_only=True)
    puesto_id = serializers.PrimaryKeyRelatedField(
        queryset=Puesto.objects.all(),
        source='puesto',
        write_only=True,
        required=False,
        allow_null=True
    )
    # Cambia unidad a read_only y agrega unidad_id para escritura
    unidad = serializers.SerializerMethodField(read_only=True)
    unidad_id = serializers.PrimaryKeyRelatedField(
        queryset=UnidadEducativa.objects.all(),
        source='unidad',
        write_only=True,
        required=False,
        allow_null=True
    )
    colegio = ColegioSerializer(read_only=True)
    colegio_id = serializers.PrimaryKeyRelatedField(
        queryset=Colegio.objects.all(), source='colegio', write_only=True,
        required=False, allow_null=True,
    )

    def get_unidad(self, obj):
        if obj.unidad:
            # Devuelve todos los campos relevantes de la unidad educativa, incluyendo el colegio anidado
            return {
                "id": obj.unidad.id,
                "nombre": obj.unidad.nombre,
                "codigo_sie": obj.unidad.codigo_sie,
                "turno": obj.unidad.turno,
                "direccion": obj.unidad.direccion,
                "telefono": obj.unidad.telefono,
                "nivel": obj.unidad.nivel,
                "colegio": ColegioSerializer(obj.unidad.colegio).data if obj.unidad.colegio else None,
            }
        return None

    class Meta:
        model = Admin
        fields = [
            'usuario_id', 'usuario',
            'puesto_id', 'puesto',
            'unidad_id', 'unidad', 'colegio_id', 'colegio',
            'estado'
        ]

    def validate(self, attrs):
        puesto = attrs.get('puesto', getattr(self.instance, 'puesto', None))
        unidad = attrs.get('unidad', getattr(self.instance, 'unidad', None))
        colegio = attrs.get('colegio', getattr(self.instance, 'colegio', None))
        nombre = puesto.nombre.strip().lower().replace('í', 'i') if puesto else ''
        if nombre in {'director', 'secretaria'} and not colegio:
            raise serializers.ValidationError({'colegio_id': 'El colegio es obligatorio.'})
        if colegio and colegio.estado != Colegio.Estado.ACTIVO:
            raise serializers.ValidationError({'colegio_id': 'El colegio seleccionado no está activo.'})
        if nombre == 'secretaria' and not unidad:
            raise serializers.ValidationError({'unidad_id': 'La unidad educativa es obligatoria para Secretaría.'})
        if unidad and colegio and unidad.colegio_id != colegio.pk:
            raise serializers.ValidationError({
                'unidad_id': 'La unidad educativa debe pertenecer al colegio seleccionado.'
            })
        return attrs

    def create(self, validated_data):
        admin = super().create(validated_data)
        admin.usuario.unidad = admin.unidad
        admin.usuario.save(update_fields=['unidad'])
        return admin

    def update(self, instance, validated_data):
        admin = super().update(instance, validated_data)
        admin.usuario.unidad = admin.unidad
        admin.usuario.save(update_fields=['unidad'])
        return admin

class AccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accion
        fields = ['id', 'nombre']

class ModeloPermitidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeloPermitido
        fields = ['id', 'nombre']

class PermisoRolSerializer(serializers.ModelSerializer):
    rol = serializers.PrimaryKeyRelatedField(read_only=True)
    modelo = serializers.PrimaryKeyRelatedField(read_only=True)
    accion = serializers.PrimaryKeyRelatedField(read_only=True)
    rol_nombre    = serializers.CharField(source='rol.nombre', read_only=True)
    modelo_nombre = serializers.CharField(source='modelo.nombre', read_only=True)
    accion_nombre = serializers.CharField(source='accion.nombre', read_only=True)

    rol_id = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.all(),
        source='rol',
        write_only=True
    )
    modelo_id = serializers.PrimaryKeyRelatedField(
        queryset=ModeloPermitido.objects.all(),
        source='modelo',
        write_only=True
    )
    accion_id = serializers.PrimaryKeyRelatedField(
        queryset=Accion.objects.all(),
        source='accion',
        write_only=True
    )

    class Meta:
        model  = PermisoRol
        fields = [
            'id',
            'rol', 'rol_id', 'rol_nombre',
            'modelo', 'modelo_id', 'modelo_nombre',
            'accion', 'accion_id', 'accion_nombre',
        ]

class PermisoPuestoSerializer(serializers.ModelSerializer):
    puesto = PuestoSerializer(read_only=True)
    puesto_id = serializers.PrimaryKeyRelatedField(
        queryset=Puesto.objects.all(),
        source='puesto',
        write_only=True
    )
    modelo = ModeloPermitidoSerializer(read_only=True)
    modelo_id = serializers.PrimaryKeyRelatedField(
        queryset=ModeloPermitido.objects.all(),
        source='modelo',
        write_only=True
    )
    accion = AccionSerializer(read_only=True)
    accion_id = serializers.PrimaryKeyRelatedField(
        queryset=Accion.objects.all(),
        source='accion',
        write_only=True
    )

    class Meta:
        model = PermisoPuesto
        fields = ['id', 'puesto', 'puesto_id', 'modelo', 'modelo_id', 'accion', 'accion_id']


# ──────────────────────────────────────────────────────────────
#  HU-SE02: payloads de gestión granular de roles
# ──────────────────────────────────────────────────────────────

class PermisoComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermisoComponente
        fields = ['id', 'componente', 'visible', 'editable']
        read_only_fields = ['id']


class RolPermisosPayloadSerializer(serializers.Serializer):
    """Reemplazo completo de los permisos funcionales de un rol."""

    permisos = serializers.ListField(child=serializers.DictField(), allow_empty=True)

    def validate_permisos(self, value):
        from .models import Accion as AccionModel, ModeloPermitido as ModeloModel
        limpios = []
        for par in value:
            modelo_nombre = str(par.get('modelo', '')).strip()
            accion_nombre = str(par.get('accion', '')).strip()
            if not modelo_nombre or not accion_nombre:
                raise serializers.ValidationError(
                    'Cada permiso requiere "modelo" y "accion".',
                )
            if not ModeloModel.objects.filter(nombre=modelo_nombre).exists():
                raise serializers.ValidationError(
                    f'Modelo desconocido: "{modelo_nombre}".',
                )
            if not AccionModel.objects.filter(nombre=accion_nombre).exists():
                raise serializers.ValidationError(
                    f'Acción desconocida: "{accion_nombre}".',
                )
            limpios.append((modelo_nombre, accion_nombre))
        # Eliminar duplicados preservando el orden.
        vistos = set()
        unicos = []
        for par in limpios:
            if par not in vistos:
                vistos.add(par)
                unicos.append(par)
        return unicos


class RolComponentesPayloadSerializer(serializers.Serializer):
    """Reemplazo completo de los componentes de interfaz de un rol."""

    componentes = serializers.ListField(child=serializers.DictField(), allow_empty=True)

    def validate_componentes(self, value):
        limpios = []
        vistos = set()
        for item in value:
            componente = str(item.get('componente', '')).strip()
            if not componente:
                raise serializers.ValidationError(
                    'Cada componente requiere el campo "componente".',
                )
            if len(componente) > 100:
                raise serializers.ValidationError(
                    'El código del componente no puede exceder 100 caracteres.',
                )
            if componente in vistos:
                continue
            vistos.add(componente)
            limpios.append({
                'componente': componente,
                'visible': bool(item.get('visible', True)),
                'editable': bool(item.get('editable', False)),
            })
        return limpios


class AsignarRolesSerializer(serializers.Serializer):
    """Reemplazo completo de los roles adicionales de un usuario."""

    rol_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)

    def validate_rol_ids(self, value):
        from .models import Rol as RolModel
        roles = list(RolModel.objects.filter(pk__in=value))
        if len(roles) != len(set(value)):
            raise serializers.ValidationError('Algunos roles no existen.')
        return roles

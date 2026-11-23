"""Alta institucional pública con verificación de correo opcional."""
import logging
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from aplicaciones.institucion.models import Colegio
from aplicaciones.suscripciones import qr_simulado, stripe_checkout, vendis
from aplicaciones.suscripciones.models import MetodoPago, Pago, Plan, Suscripcion
from aplicaciones.suscripciones.serializers import proximo_vencimiento_contratacion
from .models import Admin, Puesto, RegistroInstitucional, Rol, Usuario

logger = logging.getLogger(__name__)


class RegistroThrottle(SimpleRateThrottle):
    scope = 'registro_institucional'
    rate = '10/hour'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class RegistroSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    username = serializers.RegexField(r'^[A-Za-z0-9_.-]{3,50}$', max_length=50)
    email = serializers.EmailField(max_length=100)
    telefono_responsable = serializers.RegexField(r'^\+[1-9][0-9]{6,14}$')
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    colegio = serializers.CharField(max_length=100)
    pais = serializers.RegexField(r'^[A-Z]{2}$')
    region = serializers.CharField(max_length=100)
    ciudad = serializers.CharField(max_length=100)
    direccion = serializers.CharField(max_length=500)
    telefono = serializers.RegexField(r'^\+[1-9][0-9]{6,14}$')
    zona_horaria = serializers.CharField(max_length=50)
    idioma = serializers.ChoiceField(choices=['es', 'en'])
    razon_facturacion = serializers.CharField(max_length=150)
    email_facturacion = serializers.EmailField(max_length=254)
    identificacion_fiscal = serializers.CharField(max_length=60, required=False, allow_blank=True)
    acepta_condiciones = serializers.BooleanField()
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.filter(estado=Plan.Estado.ACTIVO, eliminado_at__isnull=True), required=False, allow_null=True)
    metodo_pago = serializers.ChoiceField(choices=Pago.Metodo.choices, required=False, allow_blank=True)
    pago_referencia = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate(self, data):
        if not data['acepta_condiciones']:
            raise serializers.ValidationError({'acepta_condiciones': 'Debe aceptar las condiciones.'})
        try:
            ZoneInfo(data['zona_horaria'])
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError({'zona_horaria': 'Indique una zona horaria válida.'})
        data['email'] = data['email'].lower()
        if Usuario.objects.filter(email__iexact=data['email']).exists():
            raise serializers.ValidationError({'email': 'Ya existe una cuenta con este correo.'})
        data['username'] = data['username'].strip()
        if Usuario.objects.filter(username__iexact=data['username']).exists():
            raise serializers.ValidationError({'username': 'Ese usuario ya está en uso.'})
        plan = data.get('plan')
        metodo = data.get('metodo_pago')
        if plan and plan.precio > 0:
            if not metodo:
                raise serializers.ValidationError({'metodo_pago': 'Seleccione un método de pago para este plan.'})
            if not MetodoPago.objects.filter(codigo=metodo, activo=True).exists():
                raise serializers.ValidationError({'metodo_pago': 'El método de pago seleccionado no está disponible.'})
            if metodo == Pago.Metodo.STRIPE and (not stripe_checkout.configurado() or plan.moneda not in stripe_checkout.MONEDAS):
                raise serializers.ValidationError({'metodo_pago': 'Stripe no está disponible para este plan.'})
            if metodo == Pago.Metodo.PASARELA and (plan.moneda != 'BOB' or not vendis.configurado()):
                raise serializers.ValidationError({'metodo_pago': 'La pasarela QR no está disponible para este plan.'})
            if metodo == Pago.Metodo.QR_SIMULADO and not qr_simulado.plan_habilitado(plan.pk, plan.precio):
                raise serializers.ValidationError({'metodo_pago': 'El QR simulado no está disponible para este plan.'})
            if metodo not in (Pago.Metodo.STRIPE, Pago.Metodo.QR_SIMULADO) and not data.get('pago_referencia', '').strip():
                raise serializers.ValidationError({'pago_referencia': 'No fue posible preparar la referencia de pago.'})
        try:
            validate_password(data['password'])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)})
        return data


def enviar_verificacion(registro):
    if settings.ENVIRONMENT == 'production' and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
        return False
    token = signing.dumps({'registro': registro.pk}, salt='registro-institucional')
    enlace = f'{settings.FRONTEND_PUBLIC_URL}/verificar-correo?token={token}'
    try:
        return bool(send_mail(
            'Verifica tu cuenta institucional',
            f'Confirma tu correo en el siguiente enlace (válido por 24 horas):\n\n{enlace}',
            settings.DEFAULT_FROM_EMAIL, [registro.usuario.email], fail_silently=False,
        ))
    except Exception as exc:
        logger.warning('El proveedor de correo no pudo enviar la verificación (%s).', type(exc).__name__)
        return False


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([RegistroThrottle])
def registrar_institucion(request):
    serializer = RegistroSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data
    plan = d.get('plan')
    con_stripe = bool(plan and plan.precio > 0 and d.get('metodo_pago') == Pago.Metodo.STRIPE)
    con_qr_simulado = bool(plan and plan.precio > 0 and d.get('metodo_pago') == Pago.Metodo.QR_SIMULADO)
    try:
        with transaction.atomic():
            colegio = Colegio.objects.create(nombre=d['colegio'], pais=d['pais'], region=d['region'],
                ciudad=d['ciudad'], direccion=d['direccion'], telefono=d['telefono'],
                zona_horaria=d['zona_horaria'], idioma=d['idioma'], razon_facturacion=d['razon_facturacion'],
                email_facturacion=d['email_facturacion'], identificacion_fiscal=d.get('identificacion_fiscal', ''),
                requiere_suscripcion=True)
            rol = Rol.objects.get(nombre='Admin', colegio__isnull=True)
            puesto = Puesto.objects.get(nombre='Director')
            ident = uuid4().hex
            usuario = Usuario.objects.create_user(ci='R' + ident[:19], username=d['username'],
                email=d['email'], nombre=d['nombre'], apellido=d['apellido'], password=d['password'],
                telefono=d['telefono_responsable'], rol=rol, is_active=True, debe_cambiar_password=False)
            Admin.objects.create(usuario=usuario, colegio=colegio, puesto=puesto)
            registro = RegistroInstitucional.objects.create(usuario=usuario, colegio=colegio, plan_seleccionado=d.get('plan'), condiciones_aceptadas_at=timezone.now())
            if plan is not None:
                inicio = timezone.localdate()
                es_gratuito = plan.precio == 0
                suscripcion = Suscripcion.objects.create(
                    colegio=colegio, plan=plan, precio_periodico=plan.precio,
                    moneda=plan.moneda, periodicidad=plan.periodicidad,
                    modulos_habilitados=list(plan.modulos_habilitados or []),
                    limite_usuarios=plan.limite_usuarios, limite_unidades=plan.limite_unidades,
                    fecha_inicio=inicio,
                    fecha_vencimiento=proximo_vencimiento_contratacion(plan, inicio),
                    estado=Suscripcion.Estado.ACTIVA if es_gratuito else Suscripcion.Estado.PENDIENTE,
                )
                if not (es_gratuito or con_stripe or con_qr_simulado):
                    Pago.objects.create(
                        suscripcion=suscripcion, metodo=d['metodo_pago'],
                        referencia=d['pago_referencia'].strip(), monto=plan.precio,
                        moneda=plan.moneda, fecha=inicio,
                        observacion='Pago iniciado durante el registro institucional.',
                    )
    except IntegrityError:
        return Response({'detail': 'No fue posible registrar la cuenta. Revise los datos e inténtelo nuevamente.'}, status=400)
    respuesta = {'detail': 'Cuenta institucional creada. Ya puedes iniciar sesión con tu usuario o correo y contraseña.'}
    correo_enviado = enviar_verificacion(registro)
    if not correo_enviado:
        respuesta['modo_correo'] = 'no_disponible'
    elif settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
        respuesta['modo_correo'] = 'consola'
    if con_stripe:
        try:
            respuesta.update(stripe_checkout.iniciar_checkout(suscripcion.pk))
        except APIException:
            respuesta['checkout_pendiente'] = True
    if con_qr_simulado:
        respuesta['qr_simulado_pendiente'] = True
    return Response(respuesta, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([RegistroThrottle])
def reenviar_verificacion(request):
    email = str(request.data.get('email', '')).strip()
    if len(email) <= 100:
        registro = RegistroInstitucional.objects.select_related('usuario').filter(
            usuario__email__iexact=email, verificado_at__isnull=True).first()
        if registro:
            enviar_verificacion(registro)
    return Response({'detail': 'Si existe un registro pendiente, recibirá un correo de verificación.'})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([RegistroThrottle])
def verificar_correo(request):
    token = request.data.get('token')
    if not isinstance(token, str) or len(token) > 1000:
        return Response({'detail': 'Enlace inválido.'}, status=400)
    try:
        data = signing.loads(token, salt='registro-institucional', max_age=24 * 60 * 60)
        with transaction.atomic():
            registro = RegistroInstitucional.objects.select_for_update().select_related('usuario').get(pk=data['registro'])
            if registro.verificado_at:
                return Response({'detail': 'El enlace ya fue utilizado.'}, status=400)
            registro.verificado_at = timezone.now()
            registro.save(update_fields=['verificado_at'])
            registro.usuario.is_active = True
            registro.usuario.save(update_fields=['is_active'])
    except (signing.BadSignature, RegistroInstitucional.DoesNotExist, KeyError, TypeError, ValueError):
        return Response({'detail': 'El enlace es inválido o ha vencido.'}, status=400)
    return Response({'detail': 'Correo verificado. Ya puedes iniciar sesión.', 'plan': registro.plan_seleccionado_id})

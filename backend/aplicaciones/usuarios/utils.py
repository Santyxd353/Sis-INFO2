import hashlib
import hmac

from django.conf import settings

from .models import Bitacora


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded and request.META.get('REMOTE_ADDR') in getattr(settings, 'TRUSTED_PROXY_IPS', set()):
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def seudonimizar_ip(ip):
    if not ip:
        return None
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'), str(ip).encode('utf-8'), hashlib.sha256,
    ).hexdigest()[:39]


def registrar_bitacora(usuario, ip, tabla_afectada, accion, descripcion):
    if not getattr(usuario, 'is_authenticated', False):
        return None

    acciones = {
        'ver': 'listar',
        'inscribir': 'crear',
        'cambiar_inscripcion': 'editar',
        'cambio_curso': 'editar',
    }
    return Bitacora.objects.create(
        usuario=usuario,
        ip=seudonimizar_ip(ip),
        tabla_afectada=tabla_afectada,
        accion=acciones.get(accion, accion if accion in {'crear', 'editar', 'eliminar', 'listar'} else 'otro'),
        # La bitácora heredada conserva una referencia técnica, no nombres ni
        # valores de negocio. El detalle seguro vive en EventoAuditoria.
        descripcion=f'Acción registrada en {tabla_afectada}',
    )

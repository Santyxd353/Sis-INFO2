"""HU-movil Fase 3: registro de dispositivos y envio de notificaciones push.

Usa el servicio de push de Expo (https://exp.host/--/api/v2/push/send), que
no requiere credenciales propias de Firebase/APNs mientras los dispositivos
se registren con un token de Expo (vale para Expo Go y para builds con EAS
que usen el servicio de push de Expo en vez de FCM/APNs directo).
"""
import logging

import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DispositivoNotificacion

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'
_PLATAFORMAS_VALIDAS = {valor for valor, _ in DispositivoNotificacion.Plataforma.choices}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def registrar_dispositivo(request):
    """Registra o actualiza el token de push del dispositivo actual."""
    token = str(request.data.get('token', '')).strip()
    plataforma = str(request.data.get('plataforma', '')).strip().upper()
    if not token:
        return Response({'token': ['Este campo es obligatorio.']}, status=status.HTTP_400_BAD_REQUEST)
    if plataforma not in _PLATAFORMAS_VALIDAS:
        return Response(
            {'plataforma': [f'Debe ser una de: {sorted(_PLATAFORMAS_VALIDAS)}.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    DispositivoNotificacion.objects.update_or_create(
        token=token,
        defaults={'usuario': request.user, 'plataforma': plataforma, 'activo': True},
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def desregistrar_dispositivo(request):
    """Desactiva el token (p.ej. al cerrar sesión). Solo afecta tokens del
    propio usuario; nunca borra el registro, por trazabilidad."""
    token = str(request.data.get('token', '')).strip()
    if not token:
        return Response({'token': ['Este campo es obligatorio.']}, status=status.HTTP_400_BAD_REQUEST)
    DispositivoNotificacion.objects.filter(token=token, usuario=request.user).update(activo=False)
    return Response(status=status.HTTP_204_NO_CONTENT)


def enviar_notificacion(usuarios, titulo, cuerpo, datos=None):
    """Envía una notificación push a los dispositivos activos de los
    usuarios dados (acepta instancias de Usuario o ids).

    Nunca lanza excepción: una notificación fallida (Expo caído, token
    inválido, sin red) no debe tumbar la operación que la origina, como
    generar un boletín.
    """
    tokens = list(
        DispositivoNotificacion.objects.filter(usuario__in=usuarios, activo=True)
        .values_list('token', flat=True),
    )
    if not tokens:
        return

    mensajes = [
        {
            'to': token,
            'title': titulo,
            'body': cuerpo,
            'data': datos or {},
            'channelId': 'default-v2',
        }
        for token in tokens
    ]
    # Expo acepta como máximo cien mensajes por solicitud. Un lote fallido
    # no impide enviar los siguientes ni revierte la operación del dominio.
    for inicio in range(0, len(mensajes), 100):
        try:
            respuesta = requests.post(EXPO_PUSH_URL, json=mensajes[inicio:inicio + 100], timeout=5)
            respuesta.raise_for_status()
        except requests.RequestException:
            logger.warning('No fue posible enviar la notificación push vía Expo.', exc_info=True)

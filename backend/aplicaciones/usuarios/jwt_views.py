from django.conf import settings
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.views import TokenRefreshView

from .auditoria import registrar_evento
from .models import Usuario


class AuditedTokenRefreshView(TokenRefreshView):
    """Renueva JWT y deja evidencia tanto del éxito como del rechazo."""

    def _usuario_del_refresh(self, raw_token):
        try:
            payload = UntypedToken(raw_token)
            usuario_id = payload.get(settings.SIMPLE_JWT.get('USER_ID_CLAIM', 'user_id'))
            return Usuario.objects.filter(pk=usuario_id).first()
        except (TokenError, TypeError, ValueError):
            return None

    def post(self, request, *args, **kwargs):
        raw_token = request.data.get('refresh', '')
        usuario = self._usuario_del_refresh(raw_token)
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError) as exc:
            registrar_evento(
                accion='TOKEN_RECHAZADO', entidad='AUTENTICACION', request=request,
                usuario=usuario, cambios={'resultado': 'REFRESH_INVALIDO'},
            )
            if isinstance(exc, InvalidToken):
                raise
            raise InvalidToken({'detail': str(exc), 'code': 'token_not_valid'}) from exc
        registrar_evento(
            accion='TOKEN_RENOVADO', entidad='AUTENTICACION', request=request,
            usuario=usuario, cambios={'resultado': 'EXITOSO'},
        )
        return Response(serializer.validated_data, status=200)

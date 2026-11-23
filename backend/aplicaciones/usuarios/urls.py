from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views, roles_views, registro_api
from .auditoria_api import EventoAuditoriaViewSet
from .notificaciones import desregistrar_dispositivo, registrar_dispositivo
from .jwt_views import AuditedTokenRefreshView


router = DefaultRouter()
router.register('auditoria', EventoAuditoriaViewSet, basename='auditoria')


urlpatterns = [
    path('registro-institucional/', registro_api.registrar_institucion),
    path('verificar-correo/', registro_api.verificar_correo),
    path('reenviar-verificacion/', registro_api.reenviar_verificacion),
    path('login/', api_views.login, name='login'),
    path('refresh/', AuditedTokenRefreshView.as_view(), name='token-refresh'),
    path('perfil/', api_views.perfil, name='perfil'),
    path('logout/', api_views.logout, name='logout'),
    path('admins/<int:usuario_id>/', api_views.admin_detail, name='admin-detail'),
    path('permisos-puesto/', api_views.permisos_puesto, name='permisos-puesto'),
    path('permisos-rol/', api_views.permisos_rol, name='permisos-rol'),
    path('usuarios/', api_views.usuarios, name='usuarios-lista'),
    path('usuarios/<int:pk>/', api_views.usuario_detail, name='usuario-detalle'),
    path('usuarios/<int:pk>/roles/', roles_views.asignar_roles_usuario, name='usuario-roles'),
    path('roles/', roles_views.roles, name='roles-lista'),
    path('roles/<int:pk>/', roles_views.rol_detail, name='rol-detalle'),
    path('roles/<int:pk>/permisos/', roles_views.rol_permisos, name='rol-permisos'),
    path('roles/<int:pk>/componentes/', roles_views.rol_componentes, name='rol-componentes'),
    path('roles/configuracion-institucional/', roles_views.configuracion_institucional, name='rol-configuracion-institucional'),
    path('acciones/', roles_views.acciones_catalogo, name='acciones-catalogo'),
    path('modelos-permitidos/', roles_views.modelos_catalogo, name='modelos-catalogo'),
    path('puestos/', api_views.puestos, name='puestos-lista'),
    path('dispositivos/registrar/', registrar_dispositivo, name='dispositivo-registrar'),
    path('dispositivos/desregistrar/', desregistrar_dispositivo, name='dispositivo-desregistrar'),
    path('', include(router.urls)),
]

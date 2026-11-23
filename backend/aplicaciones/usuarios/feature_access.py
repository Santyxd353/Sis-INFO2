"""Explicit feature permissions and scoped query helpers for school workflows."""
from django.db.models import Q
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from .models import PermisoPuesto, PermisoRol
from .tenancy import es_superadmin, normalizar_nombre, unidades_permitidas


def granted(user, model, action):
    if not user or not user.is_authenticated:
        return False
    if es_superadmin(user):
        return True
    from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
    from .privilegios import puede
    autorizar_acceso_modelo(user, model)
    return puede(user, model, action)


class SchoolPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def scoped(queryset, user, path):
    units = unidades_permitidas(user)
    return queryset if units is None else queryset.filter(**{f'{path}__in': units})


def id_filters(queryset, params, mapping):
    for name, path in mapping.items():
        value = params.get(name)
        if value in (None, ''):
            continue
        try:
            number = int(value)
            if number <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            raise serializers.ValidationError({name: 'Debe ser un entero positivo.'})
        queryset = queryset.filter(**{path: number})
    return queryset


def full_name(user):
    return f'{user.nombre} {user.apellido}'.strip() if user else ''


class FeaturePermission(BasePermission):
    model = ''

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method.lower() not in view.http_method_names:
            return True  # Let DRF return 405 for unsupported operations.
        action = 'listar' if request.method in ('GET', 'HEAD', 'OPTIONS') else 'crear'
        if request.method in ('PUT', 'PATCH') or getattr(view, 'action', '') in ('estado', 'aprobar', 'rechazar'):
            action = 'editar'
        return granted(request.user, self.model, action)

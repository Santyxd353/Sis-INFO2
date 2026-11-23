"""Reglas de privilegios granulares (HU-SE02).

Tres categorías base:
- SUPERADMIN: administrador de la plataforma (alcance global). No se convierte
  automáticamente en operador académico de ningún colegio.
- ADMIN_COLEGIO: administrador del colegio; solo opera dentro de su tenant.
- USUARIO_INSTITUCIONAL: usuario con rol base (Profesor, Estudiante, Tutor…)
  más roles personalizados adicionales de su colegio.

Principios:
- Denegación por defecto: un rol sin permisos no concede nada.
- Permisos efectivos = rol base ∪ roles adicionales activos (y, para
  administradores con puesto, ∪ permisos del puesto).
- Un administrador nunca puede delegar privilegios superiores a los suyos.
- Los permisos de interfaz (componentes) solo gobiernan la UI; la seguridad
  del backend se valida siempre con los permisos funcionales.
"""

from django.db.models import Q

from .models import PermisoComponente, PermisoPuesto, PermisoRol, Rol


def es_superadmin(usuario):
    from aplicaciones.usuarios.tenancy import es_superadmin as _es_superadmin
    return _es_superadmin(usuario)


def roles_efectivos(usuario):
    """Rol base + roles adicionales activos del usuario (HU-SE02 regla 5)."""
    roles = []
    colegio_id = colegio_del_usuario(usuario)
    if getattr(usuario, 'rol_id', None) and usuario.rol.activo and (
        usuario.rol.colegio_id is None or usuario.rol.colegio_id == colegio_id
    ):
        roles.append(usuario.rol)
    unidad_id = getattr(usuario, 'unidad_id', None)
    extras = usuario.roles_extras.filter(
        activo=True,
        categoria='FUNCIONAL',
    ).filter(
        Q(colegio_id__isnull=True, unidad_educativa__isnull=True)
        | Q(colegio_id=colegio_id, unidad_educativa__isnull=True)
        | Q(colegio_id=colegio_id, unidad_educativa_id=unidad_id)
    ).select_related('colegio', 'unidad_educativa') if colegio_id else usuario.roles_extras.none()
    roles.extend(extras)
    admin = getattr(usuario, 'admin', None)
    if admin is not None and admin.puesto_id and colegio_id:
        institucionales = Rol.objects.filter(
            activo=True,
            categoria='FUNCIONAL',
            puesto_id=admin.puesto_id,
            colegio_id=colegio_id,
        ).filter(
            Q(unidad_educativa__isnull=True) | Q(unidad_educativa_id=unidad_id)
        ).select_related('colegio', 'unidad_educativa')
        existentes = {rol.pk for rol in roles}
        roles.extend(rol for rol in institucionales if rol.pk not in existentes)
    return roles


def categoria_usuario(usuario):
    """Categoría base: SUPERADMIN | ADMIN_COLEGIO | USUARIO_INSTITUCIONAL."""
    if es_superadmin(usuario):
        return 'SUPERADMIN'
    if hasattr(usuario, 'admin'):
        return 'ADMIN_COLEGIO'
    return 'USUARIO_INSTITUCIONAL'


def colegio_del_usuario(user):
    from aplicaciones.suscripciones.servicios import colegio_del_usuario as _colegio
    return _colegio(user)


def permisos_funcionales(usuario):
    """Pares (modelo, accion) concedidos. None significa "todos" (SuperAdmin)."""
    if not getattr(usuario, 'is_authenticated', False):
        return set()
    if es_superadmin(usuario):
        return None
    pares = set()
    admin = getattr(usuario, 'admin', None)
    if admin is not None and admin.puesto_id:
        pares.update(
            PermisoPuesto.objects.filter(puesto_id=admin.puesto_id)
            .values_list('modelo__nombre', 'accion__nombre'),
        )
    roles_ids = [rol.pk for rol in roles_efectivos(usuario)]
    if roles_ids:
        pares.update(
            PermisoRol.objects.filter(rol_id__in=roles_ids)
            .values_list('modelo__nombre', 'accion__nombre'),
        )
    return pares


def puede(usuario, modelo, accion):
    """¿El usuario puede ejecutar `accion` sobre `modelo`? (denegación por defecto)"""
    permisos = permisos_funcionales(usuario)
    if permisos is None:
        return True
    return (modelo, accion) in permisos


def permisos_ui(usuario):
    """Componentes de interfaz efectivos del usuario (HU-SE02 regla 4).

    Fusión entre todos sus roles: visible=False si algún rol lo oculta;
    editable=True si algún rol lo habilita. Un componente sin configuración
    no aparece en la lista (se considera visible y no editable).
    """
    if not getattr(usuario, 'is_authenticated', False) or es_superadmin(usuario):
        return []
    roles_ids = [rol.pk for rol in roles_efectivos(usuario)]
    if not roles_ids:
        return []
    combinados = {}
    for fila in PermisoComponente.objects.filter(rol_id__in=roles_ids):
        actual = combinados.setdefault(
            fila.componente,
            {'componente': fila.componente, 'visible': True, 'editable': False},
        )
        if not fila.visible:
            actual['visible'] = False
        if fila.editable:
            actual['editable'] = True
    return sorted(combinados.values(), key=lambda fila: fila['componente'])


def puede_componente(usuario, componente):
    """Visibilidad de un componente: sin configuración → visible (opt-out)."""
    if es_superadmin(usuario):
        return True
    for fila in permisos_ui(usuario):
        if fila['componente'] == componente:
            return fila['visible']
    return True


def puede_editar_componente(usuario, componente):
    """Edición de un componente: denegación por defecto (sin config → no)."""
    if es_superadmin(usuario):
        return True
    for fila in permisos_ui(usuario):
        if fila['componente'] == componente:
            return fila['editable']
    return False


def validar_no_escalacion(solicitante, pares):
    """Pares (modelo, accion) que el solicitante no puede delegar (regla final).

    SuperAdmin puede delegar todo. Cualquier otro solicitante solo puede
    conceder permisos que posee efectivamente.
    """
    if es_superadmin(solicitante):
        return []
    propios = permisos_funcionales(solicitante)
    if propios is None:
        return []
    return [par for par in pares if par not in propios]


def roles_no_delegables(solicitante, roles):
    """Roles cuyos permisos el solicitante no puede delegar."""
    denegados = []
    for rol in roles:
        pares = set(
            PermisoRol.objects.filter(rol=rol)
            .values_list('modelo__nombre', 'accion__nombre'),
        )
        if validar_no_escalacion(solicitante, pares):
            denegados.append(rol)
    return denegados


def rol_asignable(rol, colegio_id=None, unidad_id=None):
    """¿El rol puede asignarse como rol adicional en el colegio indicado?"""
    if not rol.activo or rol.categoria != 'FUNCIONAL':
        return False
    if not rol.permisos.exists():
        return False
    if rol.colegio_id is None:
        return rol.unidad_educativa_id is None
    if colegio_id is not None and rol.colegio_id != colegio_id:
        return False
    if rol.unidad_educativa_id is not None and unidad_id != rol.unidad_educativa_id:
        return False
    return True


__all__ = [
    'categoria_usuario', 'colegio_del_usuario', 'es_superadmin',
    'puede', 'puede_componente', 'puede_editar_componente',
    'permisos_funcionales', 'permisos_ui', 'roles_efectivos',
    'roles_no_delegables', 'rol_asignable', 'validar_no_escalacion',
]

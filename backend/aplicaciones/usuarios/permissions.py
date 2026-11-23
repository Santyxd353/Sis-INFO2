from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import PermisoPuesto, PermisoRol, Accion, ModeloPermitido


_METHOD_TO_ACTION = {
    'GET':    'listar',
    'HEAD':   'listar',
    'OPTIONS':'listar',
    'POST':   'crear',
    'PUT':    'editar',
    'PATCH':  'editar',
    'DELETE': 'eliminar',
}


def _es_superadmin(user) -> bool:
    from .tenancy import es_superadmin
    return es_superadmin(user)


def metodo_a_accion(method: str) -> str:
    """
    Mapea el método HTTP a la acción correspondiente.
    """
    return _METHOD_TO_ACTION.get(method)

# ──────────────────────────────────────────────────────────────
#  Permisos base por tipo de usuario
# ──────────────────────────────────────────────────────────────
class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return _es_superadmin(request.user)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'admin')


class IsAdminOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u.is_authenticated:
            return False

        if hasattr(u, 'admin'):
            return True

        return _es_superadmin(u)


class IsEstudiante(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'estudiante')


class IsProfesor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'profesor')


class IsTutor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'tutor')


class IsProfesorOrTutor(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u.is_authenticated and (hasattr(u, 'profesor') or hasattr(u, 'tutor'))


class _IsRolNombre(BasePermission):
    """Permiso por nombre de rol (auxiliar, secretaria, director...).

    Concede acceso a SuperAdmin, a usuarios con perfil Admin y a cualquier
    usuario cuyo rol coincida con alguno de los nombres indicados.
    """
    roles = set()

    def has_permission(self, request, view):
        u = request.user
        if not u.is_authenticated:
            return False
        if _es_superadmin(u) or hasattr(u, 'admin'):
            return True
        nombre = str(getattr(getattr(u, 'rol', None), 'nombre', '')).strip().lower()
        return nombre in self.roles


class IsAuxiliar(_IsRolNombre):
    roles = {'auxiliar', 'auxiliar de docencia'}


class IsSecretaria(_IsRolNombre):
    roles = {'secretaria', 'secretario'}


class IsDirector(_IsRolNombre):
    roles = {'director'}


class IsPersonalAdministrativo(_IsRolNombre):
    roles = {'auxiliar', 'auxiliar de docencia', 'secretaria', 'secretario',
             'director', 'regente', 'administrativo'}


    
# ──────────────────────────────────────────────────────────────
#  PermisoPorPuesto → Admin con cargos variables
# ──────────────────────────────────────────────────────────────
class PermisoPorPuesto(BasePermission):
    """
    Consulta la tabla PermisoPuesto:
    (puesto, modelo, accion)
    """
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        # SuperAdmin bypass
        if _es_superadmin(user):
            return True

        # Política de suscripciones SaaS (HU-SE01): vigencia y módulos del
        # plan se validan en el backend, no solo en la interfaz.
        from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
        autorizar_acceso_modelo(user, getattr(view, 'basename', None) or '')

        # Solo Admin usa este permiso
        if not hasattr(user, 'admin'):
            return PermisoPorRol().has_permission(request, view)

        admin   = user.admin
        puesto  = admin.puesto
        modelo  = view.basename
        accion  = metodo_a_accion(request.method)

        if PermisoPuesto.objects.filter(
            puesto=puesto,
            modelo__nombre=modelo,
            accion__nombre=accion
        ).exists():
            return True

        # HU-SE02: además del puesto, el usuario puede tener roles
        # personalizados adicionales que también conceden permisos.
        from .privilegios import roles_efectivos
        roles_ids = [rol.pk for rol in roles_efectivos(user)]
        return PermisoRol.objects.filter(
            rol_id__in=roles_ids,
            modelo__nombre=modelo,
            accion__nombre=accion
        ).exists()
    
# ──────────────────────────────────────────────────────────────
#  PermisoPorRol → roles fijos (Estudiante, Profesor, Tutor…)
# ──────────────────────────────────────────────────────────────
class PermisoPorRol(BasePermission):
    """
    Usa (rol, modelo, accion) de la tabla PermisoRol.
    Pasa si existe al menos una fila que coincida.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        # SuperAdmin bypass
        if _es_superadmin(user):
            return True

        # Política de suscripciones SaaS (HU-SE01)
        from aplicaciones.suscripciones.servicios import autorizar_acceso_modelo
        autorizar_acceso_modelo(user, getattr(view, 'basename', None) or '')

        # Admin se delega a PermisoPorPuesto
        if hasattr(user, 'admin'):
            return True   # lo evaluará PermisoPorPuesto en la lista de permisos

        # Resto de usuarios deben tener un Rol
        if not user.rol_id:
            return False

        accion = metodo_a_accion(request.method)
        modelo = view.basename

        # HU-SE02: permisos efectivos = rol base ∪ roles adicionales activos.
        from .privilegios import roles_efectivos
        roles_ids = [rol.pk for rol in roles_efectivos(user)]
        return PermisoRol.objects.filter(
            rol_id__in=roles_ids,
            modelo__nombre=modelo,
            accion__nombre=accion
        ).exists()
    

# ──────────────────────────────────────────────────────────────
#  PermisoEstudianteView → regla específica de negocio
# ──────────────────────────────────────────────────────────────
class PermisoEstudianteView(BasePermission):
    """
    Combina:
      • SuperAdmin → todo
      • Admin      → PermisoPorPuesto
      • Otros roles → PermisoPorRol
      • Tutor      → lectura solo si está vinculado al estudiante
      • Profesor   → lectura si tutor del curso O dicta materia en ese curso
      • Estudiante → solo su propio registro
    """

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        # SuperAdmin bypass
        if _es_superadmin(user):
            return True

        # Admin → validamos con PermisoPorPuesto
        if hasattr(user, 'admin'):
            return PermisoPorPuesto().has_permission(request, view)

        # Otros roles → validamos con PermisoPorRol
        return PermisoPorRol().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        user = request.user

        # SuperAdmin / Admin ya pasaron
        if _es_superadmin(user) or hasattr(user, 'admin'):
            return True

        # Estudiante: solo suya
        if hasattr(user, 'estudiante'):
            return obj.pk == user.pk

        # Tutor: vínculo en TutorEstudiante
        if hasattr(user, 'tutor'):
            return obj.tutores.filter(tutor__usuario=user).exists()

        # Profesor: tutor del curso o dicta alguna materia en ese curso
        if hasattr(user, 'profesor'):
            prof  = user.profesor
            curso = obj.curso
            if not curso:
                return False

            # 1) Tutor del curso
            if curso.tutor_id == prof.pk:
                return True

            # 2) Profesor asignado en MateriaCurso
            from aplicaciones.academico.models import MateriaCurso
            return MateriaCurso.objects.filter(curso=curso, profesor=prof).exists()

        # Cualquier otro rol (visitante) → denegado
        return False

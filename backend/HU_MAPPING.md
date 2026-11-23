Mapeo de Historias de Usuario (HU) → Archivos actuales en el repo original

Objetivo: listar los archivos y componentes a mover/copiar al repo `sprint1_backend`.

HU-01 Configuración de la unidad educativa
- Backend (actual): [aplicaciones/institucion/models.py](DonBoscoBackend/aplicaciones/institucion/models.py#L1)
- Views: [aplicaciones/institucion/views.py](DonBoscoBackend/aplicaciones/institucion/views.py#L1)
- Serializers: (revisar) [aplicaciones/institucion/serializers.py](DonBoscoBackend/aplicaciones/institucion/serializers.py)

HU-03 Gestión de usuarios
- Backend (actual): [aplicaciones/usuarios/models.py](DonBoscoBackend/aplicaciones/usuarios/models.py)
- Views/serializers/urls: [aplicaciones/usuarios/usuario_views.py](DonBoscoBackend/aplicaciones/usuarios/usuario_views.py), [aplicaciones/usuarios/urls.py](DonBoscoBackend/aplicaciones/usuarios/urls.py)

HU-04 Autenticación y roles
- Backend (actual): `aplicaciones/usuarios/authentication.py`, `login_views.py`, permisos en `permissions.py`

HU-06 Gestión académica
- Backend (actual): [aplicaciones/calendario/*](DonBoscoBackend/aplicaciones/calendario)

HU-07 Estructura académica
- Backend (actual): [aplicaciones/academico/models.py](DonBoscoBackend/aplicaciones/academico/models.py), views, serializers

HU-08 Registro de docentes
- Backend (actual): [aplicaciones/personal/models.py](DonBoscoBackend/aplicaciones/personal/models.py), serializers, views

HU-09 Registro de estudiantes y tutores
- Backend (actual): [aplicaciones/estudiantes/models.py](DonBoscoBackend/aplicaciones/estudiantes/models.py), serializers, views

HU-10 Inscripción de estudiantes
- Backend (actual): [aplicaciones/estudiantes/views.py](DonBoscoBackend/aplicaciones/estudiantes/views.py), serializers y migración

HU-SE01 Gestionar planes, suscripciones y pagos SaaS
- Backend (app nueva): `aplicaciones/suscripciones/` (models, servicios, serializers, views, urls)
- Migraciones: `0001_initial` (tablas plan/suscripcion/pago) y `0002_permisos_hu_se01` (permisos de plataforma para Director/Secretaria/Administrador Institucional)
- Hooks de autorización: `usuarios/permissions.py` (PermisoPorPuesto y PermisoPorRol llaman a `autorizar_acceso_modelo`), `usuarios/api_views.py` (gate + límite de usuarios), `institucion/views.py` (límite de unidades en UnidadEducativaViewSet)
- Auditoría: `auditoria.py` ampliado con entidades PLAN, SUSCRIPCION, PAGO
- Tests: `aplicaciones/suscripciones/tests_hu_se01.py` (38 tests)
- Endpoints: `/api/suscripciones/planes|suscripciones|pagos/`
- Frontend: `src/api/suscripciones.ts`, `src/pages/suscripciones/SuscripcionesPage.tsx`, entrada `suscripciones` en el catálogo de módulos

Comparativa de tenancy (HU-SE01 vs base por cliente):
- El tenant sigue siendo el colegio (coincide con la base por cliente): `resolver_alcance`/`unidades_permitidas` en `usuarios/tenancy.py` delimitan datos por colegio/unidad.
- La suscripción es un atributo del colegio (tenant) y NO sustituye el aislamiento de datos: un colegio con suscripción activa solo ve sus propios datos, igual que antes.
- La novedad HU-SE01 es la política de acceso por módulos y límites del plan, aplicada en backend (no solo UI): sin suscripción → modo prototipo sin restricciones; suscripción inactiva → solo facturación; activa → gate por modulos_habilitados. SuperAdmin queda exento.
- Límites del plan (usuarios/unidades) se validan al crear registros (`validar_limite_usuarios`/`validar_limite_unidades`) y no modifican el modelo de aislamiento existente.

HU-SE02 Administrar usuarios, roles y privilegios granulares
- Backend (app existente): `aplicaciones/usuarios/` — modelos ampliados en `models.py` (Rol: colegio/activo/categoria; PermisoComponente; Usuario.roles_extras) y núcleo de reglas en `privilegios.py` (`roles_efectivos`, `permisos_funcionales`, `puede`, `permisos_ui`, `puede_componente`, `puede_editar_componente`, `validar_no_escalacion`, `roles_no_delegables`)
- Migraciones: `0013_hu_se02_roles_granulares.py` (campos/únicos/PERMISO_COMPONENTE) y `0014_hu_se02_datos.py` (acciones desactivar/aprobar/exportar/administrar; PermisoPuesto sobre `rol` para Director y Secretaria)
- API: `roles_views.py` + `urls.py` — `/api/usuarios/roles/?gestion=1|asignables=1`, `/roles/<pk>/`, `/roles/<pk>/permisos/`, `/roles/<pk>/componentes/`, `/usuarios/<pk>/roles/`, `/acciones/`, `/modelos-permitidos/`
- Serializers HU-SE02: `serializer.py` — `RolSerializer` (categoria/permisos/componentes; `Meta.validators=[]` porque DRF 3.18 auto-deriva UniqueTogetherValidator), `RolPermisosPayloadSerializer`, `RolComponentesPayloadSerializer`, `AsignarRolesSerializer`, `PermisoComponenteSerializer`; `UsuarioSerializer` ampliado con `roles_extras`, `roles_extra_ids`, `permisos_ui`, `categoria`
- Reglas aplicadas en backend: roles por colegio (tenant: admin solo crea/edita de su colegio; SuperAdmin crea roles de sistema con `colegio_id: null`), denegación por defecto (PUT reemplaza la matriz completa), prevención de escalación (403 si delega permisos/roles que no posee), múltiples roles por usuario (union para permisos efectivos; un rol inactivo no concede), 403 en endpoints y auditoría (`registrar_evento` con entidades ROL, PERMISO_ROL, PERMISO_COMPONENTE, ASIGNACION_ROLES)
- Hooks de permisos: `permissions.py` (`PermisoPorPuesto`/`PermisoPorRol` consultan ahora `roles_efectivos` = rol base ∪ roles_extras activos)
- Tests: `aplicaciones/usuarios/tests_hu_se02.py` (38 tests, en verde)
- Frontend: `src/api/roles.ts` (+ `roles.test.ts`, 14 tests), `src/pages/roles/RolesPage.tsx` (4 pestañas: roles CRUD, matriz de permisos funcionales modelo×acción, componentes de interfaz, roles adicionales por usuario), helpers `puedeComponente`/`puedeEditarComponente` en `AuthContext` (leen `permisos_ui`), tipo `permisos_ui` en `app/modelos/Usuarios.tsx`, entrada `roles` en `moduleCatalog.ts` (perfiles SUPERADMIN/DIRECTOR/SECRETARIA, alcances GLOBAL/COLEGIO, permiso `rol listar`) y ruta `/dashboard/roles` con `RequirePermission` en `App.tsx`
- Sustituye al módulo genérico "Autenticación y roles" (`/dashboard/superadmin/roles-autenticacion`, ModuloGestion): se reemplazó por `MODULO_ROLES` (ruta directa `/dashboard/roles`)

Estado de la suite backend (21/10, comparativa con línea base `se01_full_suite.txt` del 20/10 12:40):
- Base: 193 tests / 16 fallos. Actual: 313 tests / 22 fallos (14 FAIL + 8 ERROR) / 4 skipped = 16 base − 1 que ahora pasa (`test_crud_de_los_modulos_administrativos`) + 7 nuevos de la fusión del 20/10 22:41.
- Los 7 fallos nuevos NO son de HU-SE02 (verificado con A/B: reproducidos con `permissions.py` revertido a su versión pre-HU-SE02): 2 tests esperan 403 para estudiante en `GET /api/academico/cursos/` pero obtienen 200 porque la migración `0003` siembra `Estudiante → curso listar` (intención de la rama fusionada: catálogo general administrativo) y 5 de `academico/test_correcciones_hu18.py` fallan con errores de negocio (400 'Faltan calificaciones en una dimensión activa', `RuntimeError` no lanzado) de la misma familia que los preexistentes de evaluación HU-15.
- Los 16 fallos base preexistentes (8 evaluación HU-15, redondeo anual, unicidad asignación docente en SQLite, 6 boletines HU-19) se conservan documentados sin corregir.
- Regresión acotada: `usuarios + suscripciones + institucion` = 144/144 OK. Frontend: `tsc` OK, `eslint` OK, vitest 246/246.

Sugerencia de migración de código:
1. Copiar modelos y serializers primero en `sprint1_backend/aplicaciones/` respetando nombres de apps.
2. Copiar ViewSets y `urls.py` y ajustar import paths (startproject nombre `project`).
3. Añadir los middlewares y settings esenciales en `project/settings.py`.
4. Ejecutar migraciones y probar endpoints con `curl` o Postman.

Nota: los enlaces arriba son referencias relativas al repo actual; revisa y copia los archivos listados.

# Comunicados y alertas (HU27 / HU28)

Accesos en los menús de todos los perfiles conocidos, dentro del grupo Comunicaciones:

- `/dashboard/comunicaciones`: listado paginado, detalle y confirmación explícita de lectura.
- `/dashboard/notificaciones`: bandeja durable, filtros por categoría y sin leer, contador y preferencias de push.
- `/dashboard/comunicaciones?comunicado=ID`: detalle autenticado desde la bandeja.

Se utiliza el cliente Axios/JWT existente y el prefijo `/api/comunicacion/`. No se registran lecturas al abrir el detalle. Marcar una notificación como leída y confirmar un comunicado son acciones independientes.

La confirmación requiere `es_destinatario: true` en el detalle autenticado. El indicador refleja la audiencia fijada al publicar y permite confirmar también al director destinatario, aunque gestione el comunicado. Si el indicador falta o es falso, no se ofrece confirmación.

## Dirección

Solo el perfil Director, con alcance Colegio o Unidad, colegio asignado y permiso `comunicacion/gestionar`, muestra creación y emisión manual. Las acciones de cada comunicado requieren además `puede_gestionar` del servidor. Borradores se crean o editan con POST/PATCH; publicación y archivo requieren una confirmación adicional. Solo se archivan publicados. Publicados y archivados carecen de controles de edición. Estadísticas se muestran únicamente al gestor. La API conserva la autoridad sobre permisos y aislamiento institucional.

La unidad se elige del catálogo autorizado del colegio o queda fija para alcance Unidad. Los cursos se consultan para esa unidad. El catálogo existente de estudiantes se limita visualmente a la unidad seleccionada; la API valida de nuevo estudiante y ámbito al emitir el aviso.

## Alertas administrativas

El formulario ofrece PAGO y CONTINGENCIA, dirigidos al estudiante y sus tutores mediante POST `/comunicacion/alertas/`. No crea cobros ni registra pagos. El campo `clave_evento` permanece estable ante errores y reintentos. Para reenviar el mismo evento desde otra sesión debe reutilizarse su referencia; el servidor evita duplicados por evento y destinatario.

Preferencias GET/PATCH `/comunicacion/preferencias/` controlan push; desactivar una categoría conserva sus avisos en bandeja. El contenido se muestra como texto, sin interpretar HTML. No se implementa un proveedor nuevo de push en web.

## Comprobación

`npm run test:run`, `npm run build` y `npm run lint`. Las pruebas de comunicación usan Axios MockAdapter, sin enviar push ni requerir credenciales. Cubren contrato de mutaciones, borrador, publicación/archivo, lectura explícita, conteo/filtros, preferencias, rechazo 403, reintentos, catálogo de estudiantes y referencia estable. Navegación se comprueba para los perfiles institucionales y personales.

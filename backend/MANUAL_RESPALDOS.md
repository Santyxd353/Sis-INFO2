# Respaldos de Unidad

El superadministrador encuentra **Respaldos** en el menú lateral. Puede solicitar una copia, descargar las copias terminadas y activar la programación diaria. El archivo ZIP se guarda por defecto en `backend/private_storage/respaldos`; contiene `base.dump` (PostgreSQL), `manifest.json` y, cuando existen, los directorios `media` y `reportes`.

Las copias contienen información de todos los colegios y **no están cifradas por esta aplicación**. El administrador del servidor debe restringir los permisos del directorio y del sistema de archivos, cifrar el almacenamiento y mantener una segunda copia externa. La carpeta no debe servirse como archivo estático ni compartirse públicamente. Una copia local no protege contra pérdida del equipo. Las copias se conservan hasta que el administrador del servidor gestione su retención; no se borran automáticamente.

## Procesador

En Windows, `unidad.bat` inicia el procesador junto a la aplicación. Si estaba abierta antes de instalar esta función, reinicie Unidad para cargar la nueva versión. La tarea programada solo funciona mientras el procesador y PostgreSQL estén activos. Cuando se inicia después de la hora configurada, procesa la copia pendiente del día actual; no recupera automáticamente días anteriores.

En producción ejecute `python manage.py procesar_respaldos` como servicio supervisado separado (por ejemplo, mediante el administrador de servicios del servidor); debe reiniciarse tras un fallo y arrancar al iniciar el sistema. Un bloqueo de PostgreSQL evita que haya dos procesadores activos simultáneamente. La programación diaria está desactivada inicialmente y debe habilitarse en la web.

`PG_DUMP_PATH` puede apuntar al ejecutable `pg_dump`; si se omite, debe estar en PATH. Use una versión de cliente compatible con PostgreSQL. `RESPALDOS_ROOT` permite elegir otra carpeta privada separada de `media`, archivos estáticos y reportes. No cambie esa ubicación sin trasladar de forma segura las copias existentes.

Si un proceso se interrumpe, el siguiente procesador marca la ejecución anterior como fallida y no la presenta como copia válida. Revise el historial y los registros del servicio si una copia falla. No se envían alertas automáticas de correo.

## Restauración controlada

No restaure un archivo global directamente sobre la base compartida en funcionamiento. Para una prueba, descomprima el ZIP en una ubicación privada, cree una base PostgreSQL aislada y restaure `base.dump` en ella con `pg_restore`. Revise el resultado y compruebe tablas, acceso y archivos antes de planificar una recuperación real. Los archivos se copian después del volcado de la base y no constituyen una instantánea simultánea; pueden requerir conciliación. El archivo no incluye contraseñas ni configuración de infraestructura, roles globales de PostgreSQL o WAL para recuperación a un punto en el tiempo. Un archivo ZIP válido no demuestra que la restauración completa sea correcta.

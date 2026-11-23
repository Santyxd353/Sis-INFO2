# Operacion de respaldos

Los respaldos de colegio se generan como ZIP tecnico `.edubackup` con `LEEME.txt`, `manifest.json`, `resumen.json`, `datos/*.jsonl` y `checksums.json`. Se excluyen contrasenas, hashes, tokens, secretos y sesiones. Los respaldos globales contienen `base.dump` y quedan restringidos a SuperAdmin.

En desarrollo, `py manage.py runserver` inicia automaticamente el worker continuo en el proceso real del autoreloader cuando `DEBUG=True`. Vite se inicia desde el repositorio frontend. No es necesario ejecutar un comando adicional por cada respaldo.

En Azure, ejecutar `python manage.py procesar_respaldos` como worker supervisado separado del servidor web, nunca dentro de un worker web ni de una vista. En App Service Windows corresponde un WebJob continuo; en Linux/contenedor, un proceso worker separado desde la misma imagen backend. Ambos usan la misma base PostgreSQL y almacenamiento privado. El bloqueo advisory de PostgreSQL impide duplicados; las solicitudes pendientes se recuperan al reiniciar y se procesan en orden.

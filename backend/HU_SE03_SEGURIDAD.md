# HU-SE03 — Protección de autenticación y bitácora de seguridad

## Evidencia obligatoria

| Operación | Evento | Resultado mínimo |
| --- | --- | --- |
| Login correcto | `LOGIN_EXITOSO` | `EXITOSO` |
| Login rechazado | `LOGIN_FALLIDO` | `CREDENCIALES_INVALIDAS` o `CREDENCIALES_INCOMPLETAS` |
| Refresh correcto | `TOKEN_RENOVADO` | `EXITOSO` |
| Refresh rechazado | `TOKEN_RECHAZADO` | `REFRESH_INVALIDO` |
| Logout | `LOGOUT` | `EXITOSO`, `REFRESH_AUSENTE` o `REFRESH_INVALIDO` |
| Alta, cambio, baja o archivo de datos sensibles | Acción funcional | Resultado y campos permitidos |
| Reportes y exportaciones | `REPORTAR`, `EXPORTAR`, `CONSULTAR_QBE` o eventos de voz | Fuente y cantidad permitida |

Cada evento conserva el actor, el tenant, entidad, acción, resultado, hora oficial del servidor, IP con HMAC y correlación. `fecha_cliente` y `zona_cliente` son datos declarados por el navegador; no sustituyen la hora del servidor.

## Reglas de desarrollo

- Usar `registrar_evento` para cada operación sensible nueva.
- Para varios eventos en una solicitud, no crear UUID propios: el middleware entrega la misma correlación.
- No pasar contraseñas, JWT, refresh tokens, cookies, `Authorization`, CI, correo, teléfono o dirección a `cambios`.
- No usar `Bitacora` como fuente de auditoría. Solo se mantiene por compatibilidad y guarda IP seudonimizada y descripción técnica.
- La API de auditoría es solo lectura. PostgreSQL rechaza `UPDATE` y `DELETE` sobre `auditoria_evento`.

## Producción

Configurar en `backend/.env`:

```dotenv
DJANGO_ENV=production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=clave_aleatoria_de_al_menos_32_caracteres
DJANGO_ALLOWED_HOSTS=api.ejemplo.com
CORS_ALLOW_ALL_ORIGINS=false
CORS_ALLOWED_ORIGINS=https://app.ejemplo.com
TRUSTED_PROXY_IPS=10.0.0.10
```

Ejecutar migraciones con una cuenta de base de datos distinta a la cuenta usada por Django. La cuenta de Django debe tener `SELECT` e `INSERT` sobre `auditoria_evento`, sin `UPDATE`, `DELETE`, `ALTER`, `DROP`, ni privilegios de propietario. El rol de migraciones conserva los privilegios de esquema necesarios.

# EduGestión

Este repositorio reúne la API Django, la web React con PWA y la aplicación móvil Expo.

| Componente | Código y configuración |
|---|---|
| Backend | [backend](backend/README.md) |
| Web y PWA | [frontend](frontend/README.md) |
| Aplicación móvil | [mobile](mobile/README.md) |

## Desarrollo

1. Configura PostgreSQL para desarrollo. Copia `backend/.env.example` a `backend/.env` y configura los valores de tu entorno. Instala `backend/requirements.txt` en un entorno virtual y ejecuta `python manage.py migrate` y `python manage.py runserver` desde `backend/`.
2. Desde `frontend/`, ejecuta `npm ci` y `npm run dev`. Vite reenvía `/api` al backend local por defecto.
3. Desde `mobile/`, ejecuta `npm ci` y configura `EXPO_PUBLIC_API_BASE_URL` con una dirección que pueda alcanzar tu dispositivo antes de ejecutar `npm run start`.

Para los datos ficticios de desarrollo, el backend incluye `python manage.py seed_colegio_2027`. El comando `seed_datos_actuales` recibe una copia privada de datos mediante `--archivo` y requiere `--confirmar-datos-locales`.

## Producción en Azure

El dominio de la web, la PWA y la API es [gestion-escolar.172-190-151-24.sslip.io](https://gestion-escolar.172-190-151-24.sslip.io). El servicio de la VM utiliza `/opt/gestion-escolar/current`.

Compila la web con `VITE_API_BASE_URL=/api`. Prepara una versión con `backend/`, `frontend/dist/` y un entorno virtual Python que incluya `backend/requirements-production.txt`. El procedimiento de respaldo, validación y activación está en [release.py](backend/deploy/azure-native/release.py), junto con las plantillas de systemd y Nginx.

La configuración de producción reside en la VM. La base PostgreSQL, los archivos de usuario y las credenciales de Stripe y Firebase se administran fuera de Git. Para compilar la app móvil con Firebase, consulta [la guía de configuración móvil](mobile/README.md).

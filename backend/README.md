Sprint 1 - Backend (DonBosco) - Inicio desde cero

Objetivo: Crear un repositorio limpio para desarrollar las 8 historias de usuario (HU-01, HU-03, HU-04, HU-06, HU-07, HU-08, HU-09, HU-10) del sprint1.

Estructura propuesta:
- `manage.py` (Django)
- `project/` (settings, urls, wsgi, asgi)
- `aplicaciones/` (apps por dominio: usuarios, institucion, academico, estudiantes, personal, calendario)
- `requirements.txt`

Instrucciones rápidas:
1. Crear virtualenv e instalar Django + DRF
   ```powershell
   python -m venv env
   .\env\Scripts\Activate.ps1
   pip install django djangorestframework djangorestframework-simplejwt django-cors-headers
   pip freeze > requirements.txt
   ```
2. Crear proyecto Django y apps necesarias:
   ```powershell
   django-admin startproject project .
   python manage.py startapp aplicaciones.usuarios
   python manage.py startapp aplicaciones.institucion
   python manage.py startapp aplicaciones.academico
   python manage.py startapp aplicaciones.estudiantes
   python manage.py startapp aplicaciones.personal
   python manage.py startapp aplicaciones.calendario
   ```
3. Añadir apps a `project/settings.py` e inicializar migraciones.

Mover aquí los archivos relacionados con las 8 HUs descritas en `IMPLEMENTACION_HU10_INSCRIPCION.md`.

## Interpretación de reportes por voz con Gemini

El backend puede usar Gemini para traducir solicitudes en español a intenciones de reporte permitidas. La API key se configura únicamente en `backend/.env`:

```dotenv
GEMINI_API_KEY=pega_aqui_tu_clave_de_google_ai_studio
GEMINI_MODEL=gemini-2.5-flash
```

Obtén la clave en [Google AI Studio](https://aistudio.google.com/apikey), no la pongas en el frontend ni la compartas. Reinicia Django después de guardarla. Si la clave falta, Gemini no responde o su respuesta no cumple el esquema validado, se usa el intérprete determinista existente.

Gemini solo puede elegir reportes predefinidos; no genera SQL ni ejecuta acciones. La lista de estudiantes inscritos reutiliza el reporte operativo con aislamiento por unidad, requiere el permiso `reporte-ejecucion:ejecutar` y devuelve como máximo 100 filas. El texto de la solicitud se envía a Google cuando Gemini está configurado; el audio no se envía al backend.

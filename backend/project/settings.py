import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=''):
    return [value.strip() for value in os.environ.get(name, default).split(',') if value.strip()]


ENVIRONMENT = os.environ.get('DJANGO_ENV', 'development').strip().lower()
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'change-me-in-production')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
VENDIS_API_BASE_URL = os.environ.get('VENDIS_API_BASE_URL', '')
VENDIS_API_KEY = os.environ.get('VENDIS_API_KEY', '')
VENDIS_BUSINESS_CODE = os.environ.get('VENDIS_BUSINESS_CODE', '')
VENDIS_WEBHOOK_TOKEN = os.environ.get('VENDIS_WEBHOOK_TOKEN', '')
VENDIS_ENV = os.environ.get('VENDIS_ENV', 'sandbox')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
QR_DEMO_PLAN_IDS = env_list('QR_DEMO_PLAN_IDS')
FINANZAS_QR_DEMO_COLEGIO_IDS = [int(value) for value in env_list('FINANZAS_QR_DEMO_COLEGIO_IDS')]
FRONTEND_PUBLIC_URL = os.environ.get('FRONTEND_PUBLIC_URL', 'http://127.0.0.1:5173').rstrip('/')
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', False)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@localhost')
DEBUG = env_bool('DJANGO_DEBUG', ENVIRONMENT != 'production')
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1' if DEBUG else '')
if ENVIRONMENT == 'production' and (len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('django-insecure-')):
    raise ImproperlyConfigured('DJANGO_SECRET_KEY debe ser aleatoria y tener al menos 50 caracteres en producción.')
if ENVIRONMENT == 'production' and not ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS es obligatorio en producción.')
if ENVIRONMENT == 'production' and DEBUG:
    raise ImproperlyConfigured('DJANGO_DEBUG debe estar desactivado en producción.')

# En producción el proxy HTTPS debe configurarse explícitamente; no se confía
# en cabeceras reenviadas por clientes sin una configuración de proxy segura.
SESSION_COOKIE_SECURE = ENVIRONMENT == 'production'
CSRF_COOKIE_SECURE = ENVIRONMENT == 'production'
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', ENVIRONMENT == 'production')
SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD', False)
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
TRUSTED_PROXY_IPS = set(env_list('TRUSTED_PROXY_IPS'))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'aplicaciones.respaldos',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    'aplicaciones.institucion',
    'aplicaciones.usuarios',
    'aplicaciones.academico',
    'aplicaciones.personal',
    'aplicaciones.estudiantes',
    'aplicaciones.calendario',
    'aplicaciones.asistencia',
    'aplicaciones.comunicacion.apps.ComunicacionConfig',
    'aplicaciones.portal.apps.PortalConfig',
    'aplicaciones.seguimiento_academico',
    'aplicaciones.reportes.apps.ReportesConfig',
    'aplicaciones.suscripciones',
    'aplicaciones.finanzas',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'aplicaciones.usuarios.middleware.AuditCorrelationMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'project.wsgi.application'
ASGI_APPLICATION = 'project.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'colegio'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
REPORTES_PRIVATE_ROOT = os.environ.get('REPORTES_PRIVATE_ROOT', BASE_DIR / 'private_storage' / 'reportes')
RESPALDOS_ROOT = os.environ.get('RESPALDOS_ROOT', BASE_DIR / 'private_storage' / 'respaldos')
PG_DUMP_PATH = os.environ.get('PG_DUMP_PATH', 'pg_dump')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'usuarios.Usuario'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=int(os.environ.get('JWT_ACCESS_MINUTES', '15'))
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=int(os.environ.get('JWT_REFRESH_DAYS', '7'))
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOW_ALL_ORIGINS = env_bool('CORS_ALLOW_ALL_ORIGINS', False)
CORS_ALLOWED_ORIGINS = env_list(
    'CORS_ALLOWED_ORIGINS',
    'http://127.0.0.1:5173,http://localhost:5173' if DEBUG else '',
)
CORS_ALLOW_HEADERS = (*default_headers, 'x-client-time', 'x-client-timezone')
if ENVIRONMENT == 'production' and CORS_ALLOW_ALL_ORIGINS:
    raise ImproperlyConfigured('CORS_ALLOW_ALL_ORIGINS no puede activarse en producción.')

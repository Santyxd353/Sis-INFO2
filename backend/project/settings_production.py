"""Settings for the Linux VM; local development keeps project.settings."""

import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403


def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ImproperlyConfigured(f'{name} is required in production.')
    return value


def csv(value):
    return [item.strip() for item in value.split(',') if item.strip()]


DEBUG = False
SECRET_KEY = required('DJANGO_SECRET_KEY')
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be a strong random key of at least 50 characters.')

ALLOWED_HOSTS = csv(required('DJANGO_ALLOWED_HOSTS'))
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS or any('://' in host or '/' in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS requires explicit hostnames/IPs, without scheme or path.')
# Used only by the container health probe; port 8000 is not published.
ALLOWED_HOSTS = list(dict.fromkeys([*ALLOWED_HOSTS, 'localhost', '127.0.0.1']))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': required('POSTGRES_DB'),
        'USER': required('POSTGRES_USER'),
        'PASSWORD': required('POSTGRES_PASSWORD'),
        'HOST': os.environ.get('POSTGRES_HOST', 'db'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'connect_timeout': 5},
    }
}

STATIC_ROOT = Path(os.environ.get('DJANGO_STATIC_ROOT', '/app/staticfiles'))  # noqa: F405
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', '/app/media'))  # noqa: F405
TIME_ZONE = os.environ.get('DJANGO_TIME_ZONE', 'America/La_Paz')
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = []  # Frontend and API share the same origin.
CSRF_TRUSTED_ORIGINS = csv(os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', ''))

https_enabled = os.environ.get('DJANGO_HTTPS_ENABLED', 'true').lower()
if https_enabled not in {'true', 'false'}:
    raise ImproperlyConfigured('DJANGO_HTTPS_ENABLED must be true or false.')
SECURE_SSL_REDIRECT = https_enabled == 'true'
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_REDIRECT_EXEMPT = [r'^healthz/$']
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# This deployment controls one hostname, not every subdomain, and does not
# register the domain in browser preload lists. These two opt-in advisories
# are intentional; all other deployment checks remain enabled.
SILENCED_SYSTEM_CHECKS = ['security.W005', 'security.W021']
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}

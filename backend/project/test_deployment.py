import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase, override_settings


@override_settings(ALLOWED_HOSTS=['testserver'])
class HealthTests(SimpleTestCase):
    @patch('project.health.connection')
    def test_healthy_database(self, connection):
        response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertEqual(response['Cache-Control'], 'no-store')
        connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with('SELECT 1')

    @patch('project.health.connection')
    def test_database_failure_returns_generic_503(self, connection):
        connection.cursor.side_effect = OperationalError('private database connection details')
        response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})

    def test_probe_is_read_only(self):
        self.assertEqual(self.client.post('/healthz/').status_code, 405)


class ProductionSettingsTests(SimpleTestCase):
    def load_settings(self, **changes):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('DJANGO_', 'POSTGRES_'))}
        env.update({
            'DJANGO_SECRET_KEY': 'tests-only-0123456789abcdefghijklmnopqrstuvwxyz-ABCDEFGHIJ',
            'DJANGO_ALLOWED_HOSTS': 'colegio.example.com',
            'POSTGRES_DB': 'test', 'POSTGRES_USER': 'test', 'POSTGRES_PASSWORD': 'test',
        })
        for key, value in changes.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run(
            [sys.executable, '-c',
             'import json; from project import settings_production as s; '
             'print(json.dumps({"debug": s.DEBUG, "https": s.SECURE_SSL_REDIRECT, '
             '"secure_cookie": s.SESSION_COOKIE_SECURE, "cors": s.CORS_ALLOW_ALL_ORIGINS, '
             '"engine": s.DATABASES["default"]["ENGINE"]}))'],
            cwd=Path(__file__).resolve().parent.parent,
            env=env, capture_output=True, text=True,
        )

    def test_secure_defaults_and_postgres(self):
        result = self.load_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            'debug': False, 'https': True, 'secure_cookie': True, 'cors': False,
            'engine': 'django.db.backends.postgresql',
        })

    def test_missing_or_insecure_configuration_fails_closed(self):
        for config in [
            {'DJANGO_SECRET_KEY': None}, {'DJANGO_SECRET_KEY': 'short'},
            {'DJANGO_ALLOWED_HOSTS': '*'}, {'DJANGO_ALLOWED_HOSTS': ','},
            {'DJANGO_ALLOWED_HOSTS': 'https://example.com'},
            {'POSTGRES_PASSWORD': None}, {'DJANGO_HTTPS_ENABLED': 'typo'},
        ]:
            with self.subTest(config=config):
                result = self.load_settings(**config)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ImproperlyConfigured', result.stderr)

    def test_explicit_http_smoke_mode(self):
        result = self.load_settings(DJANGO_HTTPS_ENABLED='false')
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(result.stdout)
        self.assertFalse(settings['https'])
        self.assertFalse(settings['secure_cookie'])

"""Private first-run administrator bootstrap. Run through production manage.py shell."""
import os
from pathlib import Path
import secrets
from django.conf import settings
from django.db import transaction
from aplicaciones.usuarios.models import Usuario

assert settings.DATABASES['default']['NAME'] == 'gestion_escolar'
path = Path('/var/lib/gestion-escolar/private/admin-inicial.txt')
if not path.exists() and not Usuario.objects.filter(is_superuser=True).exists():
    password = secrets.token_urlsafe(24)
    with transaction.atomic():
        Usuario.objects.create_superuser(ci='ADMIN-AZURE-001', email='admin@gestion-escolar.invalid',
            nombre='Administrador', apellido='Gestion Escolar', username='admin',
            fecha_nacimiento='1990-01-01', password=password)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            stream.write(f'URL=https://{settings.ALLOWED_HOSTS[0]}/login\nUSUARIO=admin\nCONTRASENA={password}\n')
    print(f'Initial administrator created. Credentials retained privately at {path}.')
else:
    print('Existing administrator/configuration preserved.')

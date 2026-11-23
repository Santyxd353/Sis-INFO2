import os
import django
import sys
from pathlib import Path

# Ensure project root is on sys.path when script is executed from scripts/
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()
username = 'admin'
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        ci='999999',
        email='admin@example.com',
        nombre='Admin',
        apellido='User',
        username=username,
        password='adminpass'
    )
    print('Superuser creado')
else:
    print('Superuser ya existe')

c = Client()
r = c.get('/admin/login/')
print('status', r.status_code)
print(r.content[:200])

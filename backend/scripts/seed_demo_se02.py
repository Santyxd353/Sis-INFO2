"""Seed de demostración: usuarios y contraseñas para probar la app (HU-SE02).

Uso:  python scripts/seed_demo_se02.py
Idempotente: no duplica usuarios, colegios ni unidades.

Credenciales:
  admin       / adminpass         SuperAdmin (global)
  director    / Clave-Segura-123  Director del colegio demo (gestiona roles)
  secretaria  / Clave-Segura-123  Secretaría (solo lectura de roles)
  profesor    / Clave-Segura-123  Profesor
  estudiante  / Clave-Segura-123  Estudiante
  tutor       / Clave-Segura-123  Tutor
"""
import os
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django  # noqa: E402

django.setup()

from aplicaciones.estudiantes.models import Estudiante, Tutor  # noqa: E402
from aplicaciones.institucion.models import Colegio, UnidadEducativa  # noqa: E402
from aplicaciones.personal.models import Profesor  # noqa: E402
from aplicaciones.usuarios.models import Admin, Puesto, Rol, Usuario  # noqa: E402

CLAVE = 'Clave-Segura-123'


def obtener_o_crearUsuario(username, ci, email, nombre, apellido, rol, password, unidad=None):
    usuario = Usuario.objects.filter(username=username).first()
    if usuario is None:
        usuario = Usuario.objects.create_user(
            ci=ci, email=email, nombre=nombre, apellido=apellido, username=username,
            fecha_nacimiento=date(1990, 1, 1), rol=rol, password=password,
        )
        print(f'  + usuario {username}')
    else:
        print(f'  = usuario {username} ya existía')
    if unidad is not None and usuario.unidad_id is None:
        usuario.unidad = unidad
        usuario.save(update_fields=['unidad'])
        print(f'  + unidad de {username}')
    return usuario


def main():
    print('Seed HU-SE02 (demo)')
    superadmin = None
    if not Usuario.objects.filter(username='admin').exists():
        superadmin = Usuario.objects.create_superuser(
            ci='999999', email='admin@example.com', nombre='Admin', apellido='User',
            username='admin', fecha_nacimiento=date(1980, 1, 1), password='adminpass',
        )
        print('  + superadmin admin')
    else:
        superadmin = Usuario.objects.get(username='admin')
        print('  = superadmin admin ya existía')

    colegio, _ = Colegio.objects.get_or_create(
        nombre='Colegio Demo SI2',
        defaults={'direccion': 'Av. Demo 123', 'telefono': '70000000'},
    )
    unidad, _ = UnidadEducativa.objects.get_or_create(
        codigo_sie='DEMO-SI2-01',
        defaults={'turno': 'MANANA', 'nombre': 'Unidad Demo SI2', 'colegio': colegio},
    )
    print(f'  = colegio/unidad: {colegio.nombre} / {unidad.nombre}')

    roles = {}
    for nombre in ('Admin', 'Profesor', 'Tutor', 'Estudiante'):
        rol, created = Rol.objects.get_or_create(nombre=nombre, defaults={'colegio': None})
        roles[nombre] = rol
        if created:
            print(f'  + rol base {nombre}')

    puesto_director, _ = Puesto.objects.get_or_create(nombre='Director')
    puesto_secretaria, _ = Puesto.objects.get_or_create(nombre='Secretaría')

    director = obtener_o_crearUsuario(
        'director', 'DIR-0001', 'director@example.com', 'Dir', 'Demo',
        roles['Admin'], CLAVE, unidad,
    )
    if not hasattr(director, 'admin'):
        Admin.objects.create(
            usuario=director, puesto=puesto_director, unidad=unidad,
            colegio=colegio, estado=True,
        )
        print('  + perfil Admin/Director')

    secretaria = obtener_o_crearUsuario(
        'secretaria', 'SEC-0001', 'secretaria@example.com', 'Secre', 'Demo',
        roles['Admin'], CLAVE, unidad,
    )
    if not hasattr(secretaria, 'admin'):
        Admin.objects.create(
            usuario=secretaria, puesto=puesto_secretaria, unidad=unidad,
            colegio=colegio, estado=True,
        )
        print('  + perfil Admin/Secretaría')

    profesor = obtener_o_crearUsuario(
        'profesor', 'PRF-0001', 'profesor@example.com', 'Profe', 'Demo',
        roles['Profesor'], CLAVE, unidad,
    )
    if not hasattr(profesor, 'profesor'):
        Profesor.objects.create(usuario=profesor, unidad=unidad, estado=True)
        print('  + perfil Profesor')

    estudiante = obtener_o_crearUsuario(
        'estudiante', 'EST-0001', 'estudiante@example.com', 'Alum', 'Demo',
        roles['Estudiante'], CLAVE, unidad,
    )
    if not hasattr(estudiante, 'estudiante'):
        Estudiante.objects.create(
            usuario=estudiante, unidad=unidad, rude='RUDE-DEMO-001', estado=True,
        )
        print('  + perfil Estudiante')

    tutor = obtener_o_crearUsuario(
        'tutor', 'TUT-0001', 'tutor@example.com', 'Tute', 'Demo',
        roles['Tutor'], CLAVE, unidad,
    )
    if not hasattr(tutor, 'tutor'):
        Tutor.objects.create(usuario=tutor, parentesco='PAD')
        print('  + perfil Tutor')

    print('LISTO. Usuarios disponibles:')
    print('  admin       / adminpass          (SuperAdmin)')
    print(f'  director    / {CLAVE}   (gestiona roles)')
    print(f'  secretaria  / {CLAVE}   (lectura de roles)')
    print(f'  profesor    / {CLAVE}')
    print(f'  estudiante  / {CLAVE}')
    print(f'  tutor       / {CLAVE}')
    print(f'superadmin id={superadmin.pk}, colegio={colegio.pk}, unidad={unidad.pk}')


if __name__ == '__main__':
    main()

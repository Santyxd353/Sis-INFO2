from django.db import migrations


def convertir_roles_heredados(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Usuario = apps.get_model('usuarios', 'Usuario')
    Puesto = apps.get_model('usuarios', 'Puesto')
    Admin = apps.get_model('usuarios', 'Admin')
    UnidadEducativa = apps.get_model('institucion', 'UnidadEducativa')

    rol_admin, _ = Rol.objects.get_or_create(
        nombre='Admin',
        defaults={'descripcion': 'Personal administrativo de una unidad educativa'},
    )
    unidades = list(UnidadEducativa.objects.values_list('pk', flat=True)[:2])
    unica_unidad_id = unidades[0] if len(unidades) == 1 else None

    for nombre_heredado, nombre_puesto in (
        ('director', 'Director'),
        ('secretaria', 'Secretaria'),
    ):
        puesto, _ = Puesto.objects.get_or_create(nombre=nombre_puesto)
        roles_heredados = Rol.objects.filter(nombre__iexact=nombre_heredado).exclude(pk=rol_admin.pk)
        for rol in roles_heredados:
            for usuario in Usuario.objects.filter(rol=rol):
                perfil = Admin.objects.filter(usuario_id=usuario.pk).first()
                unidad_id = usuario.unidad_id
                if not unidad_id and perfil:
                    unidad_id = perfil.unidad_id
                unidad_id = unidad_id or unica_unidad_id
                if not unidad_id:
                    # En una instalación con varias unidades no se adivina el tenant.
                    continue

                usuario.rol_id = rol_admin.pk
                usuario.unidad_id = unidad_id
                usuario.save(update_fields=['rol', 'unidad'])
                perfil, _ = Admin.objects.get_or_create(usuario_id=usuario.pk)
                perfil.puesto_id = puesto.pk
                perfil.unidad_id = unidad_id
                perfil.estado = True
                perfil.save(update_fields=['puesto', 'unidad', 'estado'])

            if not Usuario.objects.filter(rol=rol).exists():
                rol.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0004_permiso_portal_estudiante'),
    ]

    operations = [
        migrations.RunPython(convertir_roles_heredados, migrations.RunPython.noop),
    ]

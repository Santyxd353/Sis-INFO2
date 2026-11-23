from django.db import migrations


def sembrar(apps, schema_editor):
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    Accion = apps.get_model('usuarios', 'Accion')
    Rol = apps.get_model('usuarios', 'Rol')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')
    modelo, _ = Modelo.objects.get_or_create(nombre='documento-academico')
    # Tutor/Estudiante solo pueden listar y descargar (no generar) sus propios
    # boletines; get_queryset() en DocumentoAcademicoEmitidoViewSet restringe
    # el alcance a tipo=BOLETIN + su propio historial_inscripcion.
    for nombre_accion in ('listar', 'descargar'):
        accion, _ = Accion.objects.get_or_create(nombre=nombre_accion)
        for nombre_rol in ('Tutor', 'Estudiante'):
            for rol in Rol.objects.filter(nombre__iexact=nombre_rol):
                PermisoRol.objects.get_or_create(rol=rol, modelo=modelo, accion=accion)


def eliminar(apps, schema_editor):
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')
    PermisoRol.objects.filter(
        modelo__nombre='documento-academico',
        rol__nombre__in=('Tutor', 'Estudiante'),
    ).delete()


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0015_merge_hu19_hu_se02')]
    operations = [migrations.RunPython(sembrar, eliminar)]

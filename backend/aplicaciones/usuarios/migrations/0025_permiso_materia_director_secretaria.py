from django.db import migrations


def habilitar_materia_director_secretaria(apps, schema_editor):
    """Permite a Director/Secretaria crear y editar materias, y vincularlas
    a un curso (materia-curso), que hasta ahora solo tenían permiso de
    listar."""
    Puesto = apps.get_model('usuarios', 'Puesto')
    Accion = apps.get_model('usuarios', 'Accion')
    Modelo = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')

    acciones = {
        nombre: Accion.objects.get_or_create(nombre=nombre)[0]
        for nombre in ('listar', 'crear', 'editar')
    }
    modelo_materia, _ = Modelo.objects.get_or_create(nombre='materia')
    modelo_materia_curso, _ = Modelo.objects.get_or_create(nombre='materia-curso')

    for nombre_puesto in ('Director', 'Secretaria'):
        puesto, _ = Puesto.objects.get_or_create(nombre=nombre_puesto)
        for accion in acciones.values():
            PermisoPuesto.objects.get_or_create(puesto=puesto, modelo=modelo_materia, accion=accion)
        PermisoPuesto.objects.get_or_create(
            puesto=puesto, modelo=modelo_materia_curso, accion=acciones['crear'],
        )
        PermisoPuesto.objects.get_or_create(
            puesto=puesto, modelo=modelo_materia_curso, accion=acciones['editar'],
        )


def revertir(apps, schema_editor):
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    PermisoPuesto.objects.filter(modelo__nombre='materia').delete()
    PermisoPuesto.objects.filter(
        modelo__nombre='materia-curso', accion__nombre__in=('crear', 'editar'),
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0024_rol_puesto_institucional'),
    ]

    operations = [
        migrations.RunPython(habilitar_materia_director_secretaria, revertir),
    ]

# Generated manually for HU-07: additive institutional scope for subjects.

import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


def sembrar_permisos_materias(apps, schema_editor):
    Accion = apps.get_model('usuarios', 'Accion')
    ModeloPermitido = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')
    Puesto = apps.get_model('usuarios', 'Puesto')
    Rol = apps.get_model('usuarios', 'Rol')

    acciones = {nombre: Accion.objects.get_or_create(nombre=nombre)[0] for nombre in (
        'listar', 'crear', 'editar', 'desactivar',
    )}
    recursos = {
        nombre: ModeloPermitido.objects.get_or_create(nombre=nombre)[0]
        for nombre in ('materia', 'materia-curso')
    }
    for puesto_nombre in ('Director', 'Secretaria'):
        puesto, _ = Puesto.objects.get_or_create(nombre=puesto_nombre)
        for recurso in recursos.values():
            for accion in acciones.values():
                PermisoPuesto.objects.get_or_create(
                    puesto=puesto, modelo=recurso, accion=accion,
                )
    profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
    for recurso in recursos.values():
        PermisoRol.objects.get_or_create(
            rol=profesor, modelo=recurso, accion=acciones['listar'],
        )


def revertir_permisos_materias(apps, schema_editor):
    ModeloPermitido = apps.get_model('usuarios', 'ModeloPermitido')
    PermisoPuesto = apps.get_model('usuarios', 'PermisoPuesto')
    PermisoRol = apps.get_model('usuarios', 'PermisoRol')
    recursos = ModeloPermitido.objects.filter(nombre__in=('materia', 'materia-curso'))
    PermisoPuesto.objects.filter(modelo__in=recursos).delete()
    PermisoRol.objects.filter(modelo__in=recursos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('academico', '0006_hu11_gestion_asignacion_docente'),
    ]

    operations = [
        migrations.AddField(
            model_name='materia', name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='materia', name='eliminado_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='materia', name='estado',
            field=models.CharField(choices=[('ACTIVO', 'Activo'), ('INACTIVO', 'Inactivo')], default='ACTIVO', max_length=20),
        ),
        migrations.AddField(
            model_name='materia', name='unidad_educativa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='materias', to='institucion.unidadeducativa'),
        ),
        migrations.AddField(
            model_name='materia', name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name='materiacurso', name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='materiacurso', name='eliminado_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='materiacurso', name='estado',
            field=models.CharField(choices=[('ACTIVO', 'Activo'), ('INACTIVO', 'Inactivo')], default='ACTIVO', max_length=20),
        ),
        migrations.AddField(
            model_name='materiacurso', name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='materia', name='nombre', field=models.CharField(max_length=100),
        ),
        migrations.AddIndex(
            model_name='materia', index=models.Index(fields=['unidad_educativa', 'estado'], name='ix_materia_unidad_estado'),
        ),
        migrations.AddIndex(
            model_name='materiacurso', index=models.Index(fields=['curso', 'estado'], name='ix_materia_curso_estado'),
        ),
        migrations.AddConstraint(
            model_name='materia',
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower('nombre'), 'unidad_educativa',
                condition=models.Q(('eliminado_at__isnull', True), ('estado', 'ACTIVO'), ('unidad_educativa__isnull', False)),
                name='uq_materia_unidad_nombre_activo_ci',
            ),
        ),
        migrations.RunPython(sembrar_permisos_materias, revertir_permisos_materias),
    ]

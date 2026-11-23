from django.db import migrations


DIMENSIONES_OFICIALES = (
    ('SER', 'Ser', 10, 1),
    ('SABER', 'Saber', 35, 2),
    ('HACER', 'Hacer', 35, 3),
    ('DECIDIR', 'Decidir', 10, 4),
    ('AUTOEVAL', 'Autoevaluacion', 10, 5),
)


def sembrar_configuraciones_faltantes(apps, schema_editor):
    """Completa gestiones creadas antes de la siembra automática de HU-15."""
    CalendarioAcademico = apps.get_model('calendario', 'CalendarioAcademico')
    ConfiguracionEvaluacion = apps.get_model('academico', 'ConfiguracionEvaluacion')
    DimensionEvaluacion = apps.get_model('academico', 'DimensionEvaluacion')

    for calendario in CalendarioAcademico.objects.all().iterator():
        for nivel in ('PRI', 'SEC'):
            configuracion, creada = ConfiguracionEvaluacion.objects.get_or_create(
                calendario_academico_id=calendario.pk,
                nivel=nivel,
                defaults={
                    'nota_minima': 0,
                    'nota_maxima': 100,
                    'nota_aprobacion': 51,
                    'decimales': 0,
                    'regla_redondeo': 'NORMAL',
                    'estado': 'ACTIVO',
                },
            )
            if creada:
                DimensionEvaluacion.objects.bulk_create([
                    DimensionEvaluacion(
                        configuracion_id=configuracion.pk,
                        codigo=codigo,
                        nombre=nombre,
                        ponderacion=ponderacion,
                        orden=orden,
                        estado='ACTIVO',
                    )
                    for codigo, nombre, ponderacion, orden in DIMENSIONES_OFICIALES
                ])


class Migration(migrations.Migration):

    dependencies = [
        ('academico', '0007_hu07_materias_institucionales'),
        ('calendario', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(sembrar_configuraciones_faltantes, migrations.RunPython.noop),
    ]

from decimal import Decimal

from django.db import migrations, models


def actualizar_umbral_riesgo_alto(apps, schema_editor):
    """Cambia el umbral de riesgo alto de 50 a 51 (promedio < 51 = alerta roja).

    Solo se actualizan las filas que siguen con el valor anterior por defecto,
    para no pisar umbrales personalizados por una unidad educativa.
    """
    ConfiguracionRiesgo = apps.get_model('seguimiento_academico', 'ConfiguracionRiesgo')
    ConfiguracionRiesgo.objects.filter(
        umbral_riesgo_alto=Decimal('50.00')
    ).update(umbral_riesgo_alto=Decimal('51.00'))


def revertir_umbral_riesgo_alto(apps, schema_editor):
    ConfiguracionRiesgo = apps.get_model('seguimiento_academico', 'ConfiguracionRiesgo')
    ConfiguracionRiesgo.objects.filter(
        umbral_riesgo_alto=Decimal('51.00')
    ).update(umbral_riesgo_alto=Decimal('50.00'))


class Migration(migrations.Migration):
    dependencies = [
        ('seguimiento_academico', '0002_configuracionriesgo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='configuracionriesgo',
            name='umbral_riesgo_alto',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('51.00'),
                help_text='Promedio por debajo del cual el riesgo es alto (alerta roja).',
                max_digits=5,
            ),
        ),
        migrations.RunPython(actualizar_umbral_riesgo_alto, revertir_umbral_riesgo_alto),
    ]

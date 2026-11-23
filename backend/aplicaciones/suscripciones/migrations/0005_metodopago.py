from django.db import migrations, models


METODOS = (
    ('TRANSFERENCIA', 'Transferencia bancaria', 'Pago mediante transferencia bancaria.'),
    ('TARJETA', 'Tarjeta de crédito o débito', 'Simulación segura de tarjeta; no se conservan datos de la tarjeta.'),
    ('EFECTIVO', 'Efectivo', 'Pago registrado y validado por la plataforma.'),
    ('PASARELA', 'Pasarela de pago', 'Pasarela de pago en modo prueba.'),
)


def crear_metodos(apps, schema_editor):
    MetodoPago = apps.get_model('suscripciones', 'MetodoPago')
    for codigo, nombre, descripcion in METODOS:
        MetodoPago.objects.get_or_create(codigo=codigo, defaults={
            'nombre': nombre, 'descripcion': descripcion, 'activo': True,
        })


class Migration(migrations.Migration):
    dependencies = [('suscripciones', '0004_plan_moneda_suscripcion_moneda')]

    operations = [
        migrations.CreateModel(
            name='MetodoPago',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(choices=[('TRANSFERENCIA', 'Transferencia bancaria'), ('TARJETA', 'Tarjeta de crédito o débito'), ('EFECTIVO', 'Efectivo'), ('PASARELA', 'Pasarela de pago (modo prueba)')], max_length=20, unique=True)),
                ('nombre', models.CharField(max_length=100)),
                ('descripcion', models.CharField(blank=True, max_length=255)),
                ('activo', models.BooleanField(default=True)),
                ('creado_at', models.DateTimeField(auto_now_add=True)),
                ('actualizado_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'suscripciones_metodo_pago', 'ordering': ['nombre']},
        ),
        migrations.RunPython(crear_metodos, migrations.RunPython.noop),
    ]

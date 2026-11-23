from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('institucion', '0001_initial'),
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='unidad',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='usuarios',
                to='institucion.unidadeducativa',
            ),
        ),
        migrations.AddField(
            model_name='usuario',
            name='debe_cambiar_password',
            field=models.BooleanField(default=True),
        ),
    ]

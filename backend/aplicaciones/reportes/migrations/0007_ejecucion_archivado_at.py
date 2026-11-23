from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('reportes', '0006_reparar_permisos_qbe_director')]

    operations = [
        migrations.AddField(
            model_name='ejecucionreporte',
            name='archivado_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

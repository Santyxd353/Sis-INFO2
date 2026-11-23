from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('reportes', '0004_reparar_permisos_secretaria')]
    operations = [
        migrations.AddField(
            model_name='reportedefinicion',
            name='descripcion',
            field=models.TextField(blank=True, default=''),
        ),
    ]

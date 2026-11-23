from django.db import migrations


def crear_indice_actor_historico(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS ix_auditoria_usuario_fecha '
            'ON auditoria_evento (usuario, created_at);'
        )


def eliminar_indice_actor_historico(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP INDEX IF EXISTS ix_auditoria_usuario_fecha;')


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0018_hu_se03_sanitizar_bitacora_heredada'),
    ]

    operations = [
        migrations.RunPython(crear_indice_actor_historico, eliminar_indice_actor_historico),
    ]

from django.db import migrations, models


def copiar_actor_historico(apps, schema_editor):
    EventoAuditoria = apps.get_model('usuarios', 'EventoAuditoria')
    EventoAuditoria.objects.filter(usuario__isnull=False).update(
        usuario_historico=models.F('usuario')
    )


def instalar_bloqueo_postgresql(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            CREATE OR REPLACE FUNCTION bloquear_mutacion_auditoria_evento()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Los eventos de auditoría son inmutables';
            END;
            $$ LANGUAGE plpgsql;
        """)
        cursor.execute("""
            CREATE TRIGGER trg_bloquear_mutacion_auditoria_evento
            BEFORE UPDATE OR DELETE ON auditoria_evento
            FOR EACH ROW EXECUTE FUNCTION bloquear_mutacion_auditoria_evento();
        """)


def retirar_bloqueo_postgresql(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP TRIGGER IF EXISTS trg_bloquear_mutacion_auditoria_evento ON auditoria_evento;')
        cursor.execute('DROP FUNCTION IF EXISTS bloquear_mutacion_auditoria_evento();')


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0016_permiso_documento_academico_autoservicio'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventoauditoria',
            name='usuario_historico',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(copiar_actor_historico, migrations.RunPython.noop),
        migrations.RemoveField(model_name='eventoauditoria', name='usuario'),
        migrations.RenameField(
            model_name='eventoauditoria', old_name='usuario_historico', new_name='usuario',
        ),
        migrations.AddField(
            model_name='eventoauditoria',
            name='fecha_cliente',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='eventoauditoria',
            name='zona_cliente',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='bitacora',
            name='ip',
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name='Dirección IP'),
        ),
        migrations.RunPython(instalar_bloqueo_postgresql, retirar_bloqueo_postgresql),
    ]

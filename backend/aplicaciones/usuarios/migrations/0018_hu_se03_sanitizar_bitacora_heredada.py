import hashlib
import hmac
import ipaddress

from django.conf import settings
from django.db import migrations


def sanitizar_bitacora_heredada(apps, schema_editor):
    Bitacora = apps.get_model('usuarios', 'Bitacora')
    for bitacora in Bitacora.objects.exclude(ip__isnull=True).exclude(ip='').iterator():
        try:
            ipaddress.ip_address(bitacora.ip)
        except ValueError:
            continue
        bitacora.ip = hmac.new(
            settings.SECRET_KEY.encode('utf-8'), bitacora.ip.encode('utf-8'), hashlib.sha256,
        ).hexdigest()[:39]
        bitacora.descripcion = 'Acción histórica registrada'
        bitacora.save(update_fields=['ip', 'descripcion'])


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0017_hu_se03_auditoria_inmutable'),
    ]

    operations = [
        migrations.RunPython(sanitizar_bitacora_heredada, migrations.RunPython.noop),
    ]

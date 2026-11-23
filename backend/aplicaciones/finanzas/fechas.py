from zoneinfo import ZoneInfo

from django.utils import timezone

ZONA_BOLIVIA = ZoneInfo('America/La_Paz')


def hoy():
    # El proyecto corre en UTC: sin esto, desde las 20:00 de Bolivia los pagos
    # se fecharían al día siguiente y las cuotas vencerían cuatro horas antes.
    return timezone.localdate(timezone=ZONA_BOLIVIA)

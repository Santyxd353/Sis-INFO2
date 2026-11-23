from django.core.management.base import BaseCommand

from aplicaciones.finanzas.avisos import enviar_recordatorios_pago
from aplicaciones.finanzas.models import ObligacionPago, RecordatorioPago


class Command(BaseCommand):
    help = 'HU-28: avisa a las familias sus cuotas vencidas y las que vencen pronto (programar una vez al día).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=5, help='Anticipación para las cuotas por vencer.')

    def handle(self, *args, **opciones):
        for tipo in RecordatorioPago.Tipo.values:
            resultado = enviar_recordatorios_pago(ObligacionPago.objects.all(), tipo, opciones['dias'])
            self.stdout.write(
                f"{tipo}: {resultado['estudiantes_avisados']} avisados, {resultado['ya_avisados_hoy']} ya avisados hoy",
            )

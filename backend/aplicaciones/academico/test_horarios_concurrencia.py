from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from aplicaciones.usuarios.models import Usuario, EventoAuditoria
from .models import HorarioClase
from .test_horarios_hu12 import HorarioFixture


class HorarioConcurrencyTests(HorarioFixture, TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Concurrency verification requires PostgreSQL row locks.')
        type(self).setUpTestData()

    def simultaneous(self, payloads):
        barrier = Barrier(2)
        def create(payload):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(Usuario.objects.get(pk=self.director.pk))
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                barrier.wait(timeout=10)
                return client.post('/api/academico/horarios/', payload, format='json').status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            jobs = [executor.submit(create, data) for data in payloads]
            return sorted(job.result(timeout=20) for job in jobs)

    def test_concurrent_teacher_conflict_only_one_saved(self):
        self.assertEqual(self.simultaneous([
            self.payload(), self.payload(asignacion_docente=self.assignment2.pk, aula=self.room2.pk),
        ]), [201, 409])
        self.assertEqual(HorarioClase.objects.count(), 1)
        self.assertEqual(EventoAuditoria.objects.filter(entidad='HORARIO_CLASE').count(), 1)

    def test_concurrent_shared_room_only_one_saved(self):
        self.assignment2.profesor = self.other_teacher.profesor
        self.assignment2.save()
        self.assertEqual(self.simultaneous([
            self.payload(), self.payload(asignacion_docente=self.assignment2.pk),
        ]), [201, 409])
        self.assertEqual(HorarioClase.objects.count(), 1)

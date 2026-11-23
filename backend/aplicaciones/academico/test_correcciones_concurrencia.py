from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from decimal import Decimal
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import Usuario
from .models import ActividadEvaluacion, Calificacion, ResultadoTrimestral, CorreccionCalificacion


class ConcurrencyTests(SchoolFixture, TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL row locking; SQLite is not concurrency evidence.')
        type(self).setUpTestData()

    def request(self, grade, value):
        client = APIClient()
        client.force_authenticate(self.teacher)
        response = client.post('/api/academico/correcciones/', {'calificacion': grade.pk, 'valor_nuevo': value, 'motivo': 'Concurrency test'})
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def resolve_concurrently(self, ids):
        barrier = Barrier(2)
        user_id = self.director.pk
        def approve(pk):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(Usuario.objects.get(pk=user_id))
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                barrier.wait(timeout=10)
                response = client.post(f'/api/academico/correcciones/{pk}/aprobar/')
                return response.status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(approve, pk) for pk in ids]
            return [f.result(timeout=20) for f in futures]

    def test_same_request_approved_once(self):
        pk = self.request(self.grade, '80')
        self.assertEqual(sorted(self.resolve_concurrently([pk, pk])), [200, 409])
        self.assertEqual(ResultadoTrimestral.objects.get().resultado, Decimal('80'))

    def test_different_grades_do_not_lose_recalculation(self):
        activity = ActividadEvaluacion.objects.create(asignacion_docente=self.assignment, periodo=self.period, dimension=self.dimension, nombre='Segundo examen', fecha='2026-03-02', puntaje_maximo=100)
        second = Calificacion.objects.create(actividad=activity, historial_inscripcion=self.enrollment, valor=40)
        first_id = self.request(self.grade, '80')
        second_id = self.request(second, '100')
        self.assertEqual(self.resolve_concurrently([first_id, second_id]), [200, 200])
        self.assertEqual(ResultadoTrimestral.objects.get().resultado, Decimal('90'))
        self.assertEqual(CorreccionCalificacion.objects.filter(estado='APROBADA').count(), 2)

from django.test import TestCase
from rest_framework.test import APIClient

from aplicaciones.academico.models import Grado
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.hu_test_support import SchoolFixture
from aplicaciones.usuarios.models import Accion, ModeloPermitido, PermisoPuesto, Rol, Usuario


class EstructuraCursosTests(SchoolFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        modelo, _ = ModeloPermitido.objects.get_or_create(nombre='curso')
        accion, _ = Accion.objects.get_or_create(nombre='editar')
        PermisoPuesto.objects.get_or_create(puesto=cls.director.admin.puesto, modelo=modelo, accion=accion)

    def test_director_asigna_docente_de_la_unidad_y_rechaza_otra(self):
        self.client = APIClient()
        self.client.force_authenticate(self.director)
        url = f'/api/academico/cursos/{self.course.pk}/'
        respuesta = self.client.patch(url, {'tutor': self.prof.pk}, format='json')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        rol, _ = Rol.objects.get_or_create(nombre='Profesor')
        usuario = Usuario.objects.create_user(ci='otro-docente', email='otro-docente@example.com', nombre='Otro', apellido='Docente', username='otro-docente', fecha_nacimiento='1990-01-01', rol=rol, unidad=self.other_unit)
        profesor = Profesor.objects.create(usuario=usuario, unidad=self.other_unit)
        respuesta = self.client.patch(url, {'tutor': profesor.pk}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('tutor', respuesta.data)
        self.course.refresh_from_db()
        self.assertEqual(self.course.tutor_id, self.prof.pk)

    def test_nombre_inicial_conserva_numero_interno(self):
        self.assertEqual(Grado(unidad_educativa=self.unit, nivel_educativo='INI', numero=1).nombre, 'Prekínder')
        self.assertEqual(Grado(unidad_educativa=self.unit, nivel_educativo='INI', numero=2).nombre, 'Kínder')
        self.assertEqual(Grado(unidad_educativa=self.unit, nivel_educativo='PRI', numero=1).nombre, '1ro de Educación Primaria')

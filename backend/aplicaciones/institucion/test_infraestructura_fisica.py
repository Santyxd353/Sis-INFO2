from rest_framework.test import APITestCase

from aplicaciones.institucion.models import Aula, Colegio, Modulo, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import Accion, Admin, ModeloPermitido, PermisoPuesto, PermisoRol, Puesto, Rol, Usuario


class InfraestructuraFixture:
    @classmethod
    def setUpTestData(cls):
        cls.school = Colegio.objects.create(nombre='Infra School', direccion='Test', telefono='0')
        cls.unit = UnidadEducativa.objects.create(colegio=cls.school, codigo_sie='INF-A', turno='TARDE', nombre='Unidad A')
        cls.sibling = UnidadEducativa.objects.create(
            colegio=cls.school, codigo_sie='INF-A2', turno='TARDE', nombre='Unidad A2',
        )
        other_school = Colegio.objects.create(nombre='Infra Other', direccion='Test', telefono='0')
        cls.other_unit = UnidadEducativa.objects.create(colegio=other_school, codigo_sie='INF-B', turno='TARDE', nombre='Unidad B')
        admin_role, _ = Rol.objects.get_or_create(nombre='Admin')
        teacher_role, _ = Rol.objects.get_or_create(nombre='Profesor')
        def user(name, role, unit):
            return Usuario.objects.create_user(
                ci=name, email=f'{name}@example.com', nombre=name, apellido='Test', username=name,
                fecha_nacimiento='1990-01-01', rol=role, unidad=unit,
            )
        cls.director = user('infra_director', admin_role, cls.unit)
        cls.outsider = user('infra_outsider', admin_role, cls.other_unit)
        director_position, _ = Puesto.objects.get_or_create(nombre='Director')
        Admin.objects.create(usuario=cls.director, puesto=director_position, unidad=cls.unit, colegio=cls.school)
        outsider_position, _ = Puesto.objects.get_or_create(nombre='Director Other')
        Admin.objects.create(usuario=cls.outsider, puesto=outsider_position, unidad=cls.other_unit, colegio=other_school)
        cls.secretary = Usuario.objects.create_user(
            ci='infra_secretary', email='infra_secretary@example.com', nombre='Secretary', apellido='Test',
            username='infra_secretary', fecha_nacimiento='1990-01-01', rol=admin_role, unidad=cls.unit,
        )
        secretary_position, _ = Puesto.objects.get_or_create(nombre='Secretaria')
        Admin.objects.create(usuario=cls.secretary, puesto=secretary_position, unidad=cls.unit, colegio=cls.school)
        cls.regent = user('infra_regent', admin_role, cls.unit)
        regent_position, _ = Puesto.objects.get_or_create(nombre='Regente')
        Admin.objects.create(usuario=cls.regent, puesto=regent_position, unidad=cls.unit, colegio=cls.school)
        cls.teacher = user('infra_teacher', teacher_role, cls.unit)
        Profesor.objects.create(usuario=cls.teacher, unidad=cls.unit)
        super_role, _ = Rol.objects.get_or_create(nombre='SuperAdmin')
        cls.support = Usuario.objects.create_user(
            ci='support', email='support@example.com', nombre='Support', apellido='Test',
            username='support', fecha_nacimiento='1990-01-01', rol=super_role,
        )
        for resource in ('modulo', 'aula'):
            model, _ = ModeloPermitido.objects.get_or_create(nombre=resource)
            for action_name in ('listar', 'crear', 'editar', 'desactivar'):
                action, _ = Accion.objects.get_or_create(nombre=action_name)
                for user in (cls.director, cls.secretary):
                    PermisoPuesto.objects.get_or_create(puesto=user.admin.puesto, modelo=model, accion=action)
            list_action = Accion.objects.get(nombre='listar')
            PermisoPuesto.objects.get_or_create(puesto=cls.regent.admin.puesto, modelo=model, accion=list_action)
            PermisoRol.objects.get_or_create(rol=teacher_role, modelo=model, accion=list_action)


class InfraestructuraApiTests(InfraestructuraFixture, APITestCase):
    modules_url = '/api/institucion/modulos/'
    rooms_url = '/api/institucion/aulas/'

    def module_payload(self, unit=None, **extra):
        return {
            'nombre': 'Bloque Norte', 'cantidad_aulas': 3, 'pisos': 2,
            'unidad_educativa': (unit or self.unit).pk,
            **extra,
        }

    def room_payload(self, module, **extra):
        return {'modulo': module.pk, 'nombre': 'A-1', 'capacidad': 30, 'tipo': 'AUL', 'piso': 1, **extra}

    def test_director_creates_in_college_and_not_other_college(self):
        self.client.force_authenticate(self.director)
        first = self.client.post(self.modules_url, self.module_payload(), format='json')
        second = self.client.post(self.modules_url, self.module_payload(self.sibling, nombre='Bloque Sur'), format='json')
        denied = self.client.post(self.modules_url, self.module_payload(self.other_unit, nombre='Ajeno'), format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(Modulo.objects.get(pk=first.data['id']).colegio_fk_id, self.school.pk)

    def test_secretary_is_limited_to_own_unit(self):
        self.client.force_authenticate(self.secretary)
        allowed = self.client.post(self.modules_url, self.module_payload(), format='json')
        denied = self.client.post(self.modules_url, self.module_payload(self.sibling, nombre='Hermano'), format='json')
        self.assertEqual(allowed.status_code, 201, allowed.data)
        self.assertEqual(denied.status_code, 403)
        room = self.client.post(self.rooms_url, self.room_payload(Modulo.objects.get(pk=allowed.data['id'])), format='json')
        self.assertEqual(room.status_code, 201, room.data)

    def test_support_is_read_only_and_anonymous_is_rejected(self):
        self.client.force_authenticate(self.support)
        self.assertEqual(self.client.get(self.modules_url).status_code, 200)
        self.assertEqual(self.client.post(self.modules_url, self.module_payload()).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.modules_url).status_code, 401)

    def test_creation_requires_reconciled_active_module_and_case_insensitive_names(self):
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.post(self.modules_url, {'nombre': 'Sin unidad', 'cantidad_aulas': 1}, format='json').status_code, 400)
        created = self.client.post(self.modules_url, self.module_payload(), format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(self.client.post(self.modules_url, self.module_payload(nombre='  bloque norte  '), format='json').status_code, 400)
        legacy = Modulo.objects.create(nombre='Legado', cantidad_aulas=1, colegio_fk=self.school)
        self.assertEqual(self.client.post(self.rooms_url, self.room_payload(legacy), format='json').status_code, 400)
        module = Modulo.objects.get(pk=created.data['id'])
        self.assertEqual(self.client.post(self.rooms_url, self.room_payload(module), format='json').status_code, 201)
        self.assertEqual(self.client.post(self.rooms_url, self.room_payload(module, nombre=' a-1 '), format='json').status_code, 400)

    def test_filters_do_not_expand_scope_and_regent_lists_own_unit(self):
        own = Modulo.objects.create(nombre='Own', cantidad_aulas=1, colegio_fk=self.school, unidad_educativa=self.unit)
        sibling = Modulo.objects.create(nombre='Sibling', cantidad_aulas=1, colegio_fk=self.school, unidad_educativa=self.sibling)
        Aula.objects.create(modulo=own, nombre='O1', capacidad=20)
        Aula.objects.create(modulo=sibling, nombre='S1', capacidad=20)
        self.client.force_authenticate(self.secretary)
        response = self.client.get(self.rooms_url, {'unidad_educativa': self.sibling.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)
        self.client.force_authenticate(self.regent)
        response = self.client.get(self.rooms_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data['results']], [own.aulas.get().pk])

    def test_no_delete_and_deactivation_preserves_rows_and_audits(self):
        module = Modulo.objects.create(nombre='Deactivate', cantidad_aulas=1, colegio_fk=self.school, unidad_educativa=self.unit)
        room = Aula.objects.create(modulo=module, nombre='D1', capacidad=20)
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.delete(f'{self.modules_url}{module.pk}/').status_code, 405)
        self.assertEqual(self.client.post(f'{self.modules_url}{module.pk}/desactivar/').status_code, 400)
        self.assertEqual(self.client.post(f'{self.rooms_url}{room.pk}/desactivar/').status_code, 200)
        response = self.client.post(f'{self.modules_url}{module.pk}/desactivar/')
        self.assertEqual(response.status_code, 200, response.data)
        module.refresh_from_db()
        self.assertEqual(module.estado, Modulo.Estado.INACTIVO)
        self.assertIsNotNone(module.eliminado_at)

    def test_teacher_cannot_see_unrelated_rooms(self):
        module = Modulo.objects.create(nombre='Schedule', cantidad_aulas=1, colegio_fk=self.school, unidad_educativa=self.unit)
        Aula.objects.create(modulo=module, nombre='H1', capacidad=20)
        self.client.force_authenticate(self.teacher)
        response = self.client.get(self.rooms_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)

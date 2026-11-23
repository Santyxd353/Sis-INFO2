"""Tests de la HU-SE01: gestionar planes, suscripciones y pagos SaaS.

Cubre las 8 reglas de aceptación:
 1. CRUD de planes (solo Superadministrador, baja lógica e historial).
 2. Contratación de planes con snapshot de precio/módulos/límites e historial.
 3. Pagos manuales requieren validación; la pasarela requiere confirmación externa.
 4. Un solo pago VALIDADO activa o renueva la suscripción.
 5. Restricciones de funciones según el estado de la suscripción (incluye
    el gate de módulos en el backend, no solo en la interfaz).
 6. Límites de usuarios y unidades educativas del plan vigente.
 7. Bitácora y auditoría de las operaciones de la plataforma.
 8. Aislamiento de tenants (colegios) en suscripciones y pagos.
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.usuarios.models import (
    Accion, Admin, Bitacora, EventoAuditoria, ModeloPermitido, PermisoPuesto,
    Puesto, Rol, Usuario,
)

from .models import Pago, Plan, Suscripcion
from .servicios import calcular_vencimiento


class BaseSuscripcionesTests(APITestCase):
    password = 'Clave-Segura-123'
    api = '/api/suscripciones'

    @classmethod
    def setUpTestData(cls):
        cls.colegio_a = Colegio.objects.create(nombre='Colegio SaaS A')
        cls.colegio_b = Colegio.objects.create(nombre='Colegio SaaS B')
        cls.unidad_a = cls._unidad('SaaS-A1', cls.colegio_a)
        cls.unidad_b = cls._unidad('SaaS-B1', cls.colegio_b)
        cls.rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        cls.rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        cls.puesto_director, _ = Puesto.objects.get_or_create(nombre='Director')
        cls.director_a = cls._admin('DIRA', cls.unidad_a, cls.puesto_director)
        cls.director_b = cls._admin('DIRB', cls.unidad_b, cls.puesto_director)
        cls.profesor_a = cls._usuario('PROFA', cls.unidad_a, cls.rol_profesor)
        cls.superusuario = Usuario.objects.create_superuser(
            ci='SaaS-SUP', email='saas-sup@example.com', nombre='Super',
            apellido='Suscripciones', username='saas_sup', password=cls.password,
        )
        listar, _ = Accion.objects.get_or_create(nombre='listar')
        crear, _ = Accion.objects.get_or_create(nombre='crear')
        m_suscripcion, _ = ModeloPermitido.objects.get_or_create(nombre='suscripcion')
        m_pago, _ = ModeloPermitido.objects.get_or_create(nombre='pago')
        for accion in (listar, crear):
            PermisoPuesto.objects.get_or_create(
                puesto=cls.puesto_director, modelo=m_suscripcion, accion=accion,
            )
        PermisoPuesto.objects.get_or_create(
            puesto=cls.puesto_director, modelo=m_pago, accion=listar,
        )
        for nombre, accion in (('colegio', listar), ('usuario', crear)):
            modelo, _ = ModeloPermitido.objects.get_or_create(nombre=nombre)
            PermisoPuesto.objects.get_or_create(puesto=cls.puesto_director, modelo=modelo, accion=accion)

        cls.plan_basico = Plan.objects.create(
            nombre='Básico', precio=Decimal('100.00'), periodicidad='MENSUAL',
            modulos_habilitados=['colegio', 'unidad-educativa', 'usuario'],
        )
        cls.plan_restringido = Plan.objects.create(
            nombre='Escolar', precio=Decimal('50.00'), periodicidad='MENSUAL',
            modulos_habilitados=['colegio'], limite_unidades=1,
        )
        cls.plan_inactivo = Plan.objects.create(
            nombre='Legacy', precio=Decimal('10.00'), periodicidad='ANUAL',
            estado='INACTIVO',
        )

    @classmethod
    def _unidad(cls, codigo, colegio):
        return UnidadEducativa.objects.create(
            colegio=colegio, codigo_sie=codigo, turno='TARDE', nombre=codigo,
        )

    @classmethod
    def _usuario(cls, codigo, unidad, rol):
        return Usuario.objects.create_user(
            ci=f'SAAS-{codigo}', email=f'saas-{codigo.lower()}@example.com',
            nombre=codigo, apellido='SaaS', username=f'saas_{codigo.lower()}',
            password=cls.password, rol=rol, unidad=unidad,
        )

    @classmethod
    def _admin(cls, codigo, unidad, puesto):
        usuario = cls._usuario(codigo, unidad, cls.rol_admin)
        Admin.objects.create(
            usuario=usuario, unidad=unidad, colegio=unidad.colegio, puesto=puesto,
        )
        return usuario

    def _contratar(self, plan, colegio=None, as_user=None):
        self.client.force_authenticate(as_user or self.superusuario)
        payload = {'plan': plan.pk}
        if colegio is not None:
            payload['colegio'] = colegio.pk
        response = self.client.post(
            f'{self.api}/suscripciones/', payload, format='json',
        )
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED, response.data,
        )
        return Suscripcion.objects.get(pk=response.data['id'])

    def _registrar_pago(self, suscripcion, metodo='TRANSFERENCIA', **extra):
        self.client.force_authenticate(self.superusuario)
        payload = {
            'suscripcion': suscripcion.pk, 'metodo': metodo,
            'referencia': f'REF-{suscripcion.pk}', 'monto': suscripcion.precio_periodico,
        }
        payload.update(extra)
        response = self.client.post(
            f'{self.api}/pagos/', payload, format='json',
        )
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED, response.data,
        )
        return Pago.objects.get(pk=response.data['id'])

    def _activar(self, suscripcion):
        """Activa mediante una transferencia validada por el superadministrador."""
        pago = self._registrar_pago(suscripcion, metodo='TRANSFERENCIA')
        response = self.client.post(f'{self.api}/pagos/{pago.pk}/validar/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        pago.refresh_from_db()
        return pago

    def _suscripcion_activa_orm(self, colegio, **campos):
        """Crea directamente una suscripción ACTIVA (para casos de límites)."""
        hoy = timezone.localdate()
        defaults = {
            'plan': self.plan_basico,
            'precio_periodico': self.plan_basico.precio,
            'periodicidad': 'MENSUAL',
            'modulos_habilitados': [
                'colegio', 'unidad-educativa', 'usuario',
            ],
            'limite_usuarios': 0,
            'limite_unidades': 0,
            'fecha_inicio': hoy,
            'fecha_vencimiento': hoy + timedelta(days=30),
            'estado': Suscripcion.Estado.ACTIVA,
        }
        defaults.update(campos)
        return Suscripcion.objects.create(colegio=colegio, **defaults)


class GestionDePlanesTests(BaseSuscripcionesTests):
    def test_superadmin_crea_edita_y_desactiva_plan(self):
        self.client.force_authenticate(self.superusuario)
        crear = self.client.post(
            f'{self.api}/planes/',
            {
                'nombre': 'Premium', 'precio': '200.00',
                'periodicidad': 'TRIMESTRAL',
                'modulos_habilitados': ['colegio', 'usuario'],
                'limite_usuarios': 50, 'limite_unidades': 5,
            },
            format='json',
        )
        self.assertEqual(crear.status_code, status.HTTP_201_CREATED, crear.data)
        plan = Plan.objects.get(pk=crear.data['id'])
        self.assertEqual(plan.estado, Plan.Estado.ACTIVO)

        editar = self.client.patch(
            f'{self.api}/planes/{plan.pk}/', {'precio': '250.00'}, format='json',
        )
        self.assertEqual(editar.status_code, status.HTTP_200_OK, editar.data)
        plan.refresh_from_db()
        self.assertEqual(plan.precio, Decimal('250.00'))

        borrar = self.client.delete(f'{self.api}/planes/{plan.pk}/')
        self.assertEqual(borrar.status_code, status.HTTP_204_NO_CONTENT)
        plan.refresh_from_db()
        self.assertIsNotNone(plan.eliminado_at)
        self.assertEqual(plan.estado, Plan.Estado.INACTIVO)
        detalle = self.client.get(f'{self.api}/planes/{plan.pk}/')
        self.assertEqual(detalle.status_code, status.HTTP_404_NOT_FOUND)

    def test_operaciones_de_planes_dejan_auditoria_y_bitacora(self):
        self.client.force_authenticate(self.superusuario)
        crear = self.client.post(
            f'{self.api}/planes/',
            {
                'nombre': 'Auditable', 'precio': '10.00',
                'periodicidad': 'MENSUAL',
            },
            format='json',
        )
        self.assertEqual(crear.status_code, status.HTTP_201_CREATED, crear.data)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                entidad='PLAN', accion='CREAR', usuario=self.superusuario.pk,
            ).exists(),
        )
        self.assertTrue(
            Bitacora.objects.filter(
                tabla_afectada='plan', accion='crear', usuario=self.superusuario,
            ).exists(),
        )

    def test_solo_superadmin_gestiona_planes(self):
        self.client.force_authenticate(self.director_a)
        crear = self.client.post(
            f'{self.api}/planes/',
            {'nombre': 'Intruso', 'precio': '1.00', 'periodicidad': 'MENSUAL'},
            format='json',
        )
        self.assertEqual(crear.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_superadmin_solo_lista_planes_activos(self):
        self.client.force_authenticate(self.director_a)
        lista = self.client.get(f'{self.api}/planes/')
        self.assertEqual(lista.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item['nombre'] for item in lista.data},
            {'Básico', 'Escolar'},
        )


class ContratacionTests(BaseSuscripcionesTests):
    def test_contrata_genera_suscripcion_pendiente_con_snapshot(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self.assertEqual(suscripcion.estado, Suscripcion.Estado.PENDIENTE)
        self.assertEqual(suscripcion.colegio_id, self.colegio_a.pk)
        self.assertEqual(suscripcion.precio_periodico, self.plan_basico.precio)
        self.assertEqual(
            suscripcion.modulos_habilitados, self.plan_basico.modulos_habilitados,
        )
        self.assertEqual(suscripcion.limite_usuarios, self.plan_basico.limite_usuarios)
        self.assertEqual(
            suscripcion.fecha_vencimiento,
            calcular_vencimiento(timezone.localdate(), 'MENSUAL'),
        )

    def test_edicion_de_plan_no_altera_suscripciones_contratadas(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self.client.force_authenticate(self.superusuario)
        editar = self.client.patch(
            f'{self.api}/planes/{self.plan_basico.pk}/',
            {'precio': '999.00', 'modulos_habilitados': []},
            format='json',
        )
        self.assertEqual(editar.status_code, status.HTTP_200_OK, editar.data)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.precio_periodico, Decimal('100.00'))
        self.assertEqual(
            suscripcion.modulos_habilitados,
            ['colegio', 'unidad-educativa', 'usuario'],
        )

    def test_director_contrata_para_su_colegio_sin_indicarlo(self):
        suscripcion = self._contratar(
            self.plan_basico, as_user=self.director_a,
        )
        self.assertEqual(suscripcion.colegio_id, self.colegio_a.pk)

    def test_no_puede_contratar_para_otro_colegio(self):
        self.client.force_authenticate(self.director_a)
        response = self.client.post(
            f'{self.api}/suscripciones/',
            {'plan': self.plan_basico.pk, 'colegio': self.colegio_b.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Suscripcion.objects.filter(colegio=self.colegio_b).exists(),
        )

    def test_no_permite_dos_suscripciones_vigentes(self):
        self._contratar(self.plan_basico, self.colegio_a)
        self.client.force_authenticate(self.superusuario)
        repetir = self.client.post(
            f'{self.api}/suscripciones/',
            {'plan': self.plan_restringido.pk, 'colegio': self.colegio_a.pk},
            format='json',
        )
        self.assertEqual(repetir.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ya tiene una suscripción', str(repetir.data))

    def test_superadmin_debe_indicar_el_colegio_que_contrata(self):
        self.client.force_authenticate(self.superusuario)
        response = self.client.post(
            f'{self.api}/suscripciones/',
            {'plan': self.plan_basico.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_plan_inactivo_no_es_contratable(self):
        self.client.force_authenticate(self.superusuario)
        response = self.client.post(
            f'{self.api}/suscripciones/',
            {'plan': self.plan_inactivo.pk, 'colegio': self.colegio_a.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_fecha_inicio_en_pasado_no_es_contratable(self):
        self.client.force_authenticate(self.superusuario)
        ayer = timezone.localdate() - timedelta(days=1)
        response = self.client.post(
            f'{self.api}/suscripciones/',
            {
                'plan': self.plan_basico.pk, 'colegio': self.colegio_a.pk,
                'fecha_inicio': ayer.isoformat(),
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancelar_y_recontratar_conserva_historial(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self._activar(suscripcion)
        self.client.force_authenticate(self.superusuario)
        cancelar = self.client.post(
            f'{self.api}/suscripciones/{suscripcion.pk}/cancelar/',
        )
        self.assertEqual(cancelar.status_code, status.HTTP_200_OK)

        nueva = self._contratar(self.plan_restringido, self.colegio_a)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, Suscripcion.Estado.CANCELADA)
        self.assertEqual(suscripcion.pagos.count(), 1)
        self.assertEqual(nueva.estado, Suscripcion.Estado.PENDIENTE)
        self.assertEqual(nueva.precio_periodico, self.plan_restringido.precio)


class PagosTests(BaseSuscripcionesTests):
    def test_pago_manual_nace_pendiente_y_validar_activa(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self.client.force_authenticate(self.superusuario)
        crear = self.client.post(
            f'{self.api}/pagos/',
            {
                'suscripcion': suscripcion.pk, 'metodo': 'TRANSFERENCIA',
                'referencia': 'TRX-001', 'monto': '100.00',
            },
            format='json',
        )
        self.assertEqual(crear.status_code, status.HTTP_201_CREATED, crear.data)
        pago = Pago.objects.get(pk=crear.data['id'])
        self.assertEqual(pago.resultado, Pago.Resultado.PENDIENTE)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, Suscripcion.Estado.PENDIENTE)

        validar = self.client.post(f'{self.api}/pagos/{pago.pk}/validar/')
        self.assertEqual(validar.status_code, status.HTTP_200_OK, validar.data)
        pago.refresh_from_db()
        self.assertEqual(pago.resultado, Pago.Resultado.VALIDADO)
        self.assertEqual(pago.validado_por_id, self.superusuario.pk)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, Suscripcion.Estado.ACTIVA)
        self.assertEqual(
            suscripcion.fecha_vencimiento,
            calcular_vencimiento(timezone.localdate(), 'MENSUAL'),
        )

    def test_pasarela_no_se_puede_autovalidar_por_registro_manual(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        response = self.client.post(f'{self.api}/pagos/', {
            'suscripcion': suscripcion.pk, 'metodo': 'PASARELA',
            'referencia': 'FALSA', 'monto': suscripcion.precio_periodico,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, Suscripcion.Estado.PENDIENTE)

    def test_pago_validado_renueva_suscripcion_vencida(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        hoy = timezone.localdate()
        Suscripcion.objects.filter(pk=suscripcion.pk).update(
            estado=Suscripcion.Estado.VENCIDA,
            fecha_inicio=hoy - timedelta(days=60),
            fecha_vencimiento=hoy - timedelta(days=30),
        )
        suscripcion = Suscripcion.objects.get(pk=suscripcion.pk)
        self._registrar_pago(suscripcion, metodo='TRANSFERENCIA')
        self.client.force_authenticate(self.superusuario)
        pago = suscripcion.pagos.order_by('-id').first()
        validar = self.client.post(f'{self.api}/pagos/{pago.pk}/validar/')
        self.assertEqual(validar.status_code, status.HTTP_200_OK, validar.data)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, Suscripcion.Estado.ACTIVA)
        self.assertEqual(suscripcion.fecha_vencimiento, calcular_vencimiento(hoy, 'MENSUAL'))

    def test_superadmin_puede_validar_pago_administrativo_de_plan_gratuito(self):
        plan_gratuito = Plan.objects.create(
            nombre='Gratuito administrativo', precio=Decimal('0.00'),
            periodicidad='ANUAL', modulos_habilitados=['colegio'],
        )
        suscripcion = self._contratar(plan_gratuito, self.colegio_a)
        self.client.force_authenticate(self.superusuario)
        crear = self.client.post(
            f'{self.api}/pagos/',
            {
                'suscripcion': suscripcion.pk, 'metodo': 'TARJETA',
                'referencia': 'ADMIN-001', 'monto': '1.00',
            }, format='json',
        )
        self.assertEqual(crear.status_code, status.HTTP_201_CREATED, crear.data)
        validar = self.client.post(f'{self.api}/pagos/{crear.data["id"]}/validar/')
        self.assertEqual(validar.status_code, status.HTTP_200_OK, validar.data)
        self.assertEqual(validar.data['resultado'], Pago.Resultado.VALIDADO)

    def test_pago_validado_activa_desde_hoy_suscripcion_con_inicio_futuro(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        futuro = timezone.localdate() + timedelta(days=30)
        Suscripcion.objects.filter(pk=suscripcion.pk).update(
            estado=Suscripcion.Estado.ACTIVA,
            fecha_inicio=futuro,
            fecha_vencimiento=futuro + timedelta(days=365),
        )
        pago = Pago.objects.create(
            suscripcion=suscripcion, metodo='TRANSFERENCIA', referencia='FUT-001',
            monto=suscripcion.precio_periodico, moneda=suscripcion.moneda,
            fecha=timezone.localdate(), resultado=Pago.Resultado.PENDIENTE,
        )
        self.client.force_authenticate(self.superusuario)
        respuesta = self.client.post(f'{self.api}/pagos/{pago.pk}/validar/')
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.fecha_inicio, timezone.localdate())

    def test_no_se_puede_validar_un_pago_dos_veces(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        pago = self._activar(suscripcion)
        self.client.force_authenticate(self.superusuario)
        repetir = self.client.post(f'{self.api}/pagos/{pago.pk}/validar/')
        self.assertEqual(repetir.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rechazo_de_pago_no_modifica_la_suscripcion(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self.client.force_authenticate(self.superusuario)
        crear = self.client.post(
            f'{self.api}/pagos/',
            {
                'suscripcion': suscripcion.pk, 'metodo': 'EFECTIVO',
                'referencia': 'EF-001', 'monto': '100.00',
            },
            format='json',
        )
        rechazar = self.client.post(
            f'{self.api}/pagos/{crear.data["id"]}/rechazar/',
            {'motivo': 'Comprobante ilegible'}, format='json',
        )
        self.assertEqual(rechazar.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Pago.objects.get(pk=crear.data['id']).resultado,
            Pago.Resultado.RECHAZADO,
        )
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, Suscripcion.Estado.PENDIENTE)

    def test_solo_superadmin_valida_pagos(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self.client.force_authenticate(self.superusuario)
        crear = self.client.post(
            f'{self.api}/pagos/',
            {
                'suscripcion': suscripcion.pk, 'metodo': 'TRANSFERENCIA',
                'referencia': 'TRX-002', 'monto': '100.00',
            },
            format='json',
        )
        self.client.force_authenticate(self.director_a)
        validar = self.client.post(f'{self.api}/pagos/{crear.data["id"]}/validar/')
        self.assertEqual(validar.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_registra_pago_de_otro_colegio(self):
        suscripcion_b = self._contratar(self.plan_basico, self.colegio_b)
        crear, _ = Accion.objects.get_or_create(nombre='crear')
        m_pago, _ = ModeloPermitido.objects.get_or_create(nombre='pago')
        PermisoPuesto.objects.get_or_create(
            puesto=self.puesto_director, modelo=m_pago, accion=crear,
        )
        self.client.force_authenticate(self.director_a)
        response = self.client.post(
            f'{self.api}/pagos/',
            {
                'suscripcion': suscripcion_b.pk, 'metodo': 'EFECTIVO',
                'referencia': 'AJENO', 'monto': '50.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('otro colegio', str(response.data))

    def test_monto_no_positivo_es_rechazado(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self.client.force_authenticate(self.superusuario)
        response = self.client.post(
            f'{self.api}/pagos/',
            {
                'suscripcion': suscripcion.pk, 'metodo': 'EFECTIVO',
                'referencia': 'GRATIS', 'monto': '0.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RestriccionesTests(BaseSuscripcionesTests):
    def test_colegio_sin_suscripcion_no_restringe(self):
        self.client.force_authenticate(self.director_a)
        response = self.client.get('/api/institucion/colegios/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_suscripcion_pendiente_bloquea_gestion(self):
        self._contratar(self.plan_basico, self.colegio_a)
        self.client.force_authenticate(self.director_a)
        response = self.client.get('/api/institucion/colegios/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('suscripción del colegio', str(response.data))

    def test_suscripcion_suspendida_bloquea_gestion_permitiendo_facturacion(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self._activar(suscripcion)
        self.client.force_authenticate(self.superusuario)
        suspender = self.client.post(
            f'{self.api}/suscripciones/{suscripcion.pk}/suspender/',
        )
        self.assertEqual(suspender.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.director_a)
        gestion = self.client.get('/api/institucion/colegios/')
        self.assertEqual(gestion.status_code, status.HTTP_403_FORBIDDEN)
        facturacion = self.client.get(f'{self.api}/suscripciones/')
        self.assertEqual(facturacion.status_code, status.HTTP_200_OK)
        estado = self.client.get(f'{self.api}/suscripciones/mi-estado/')
        self.assertEqual(estado.status_code, status.HTTP_200_OK)
        self.assertFalse(estado.data['suscripcion_activa'])
        self.assertIsNotNone(estado.data['restriccion'])

    def test_suscripcion_activa_vencida_por_fecha_bloquea(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self._activar(suscripcion)
        hoy = timezone.localdate()
        Suscripcion.objects.filter(pk=suscripcion.pk).update(
            fecha_inicio=hoy - timedelta(days=60),
            fecha_vencimiento=hoy - timedelta(days=1),
        )
        self.client.force_authenticate(self.director_a)
        response = self.client.get('/api/institucion/colegios/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Vencida', str(response.data))

    def test_suscripcion_cancelada_bloquea_gestion(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self._activar(suscripcion)
        self.client.force_authenticate(self.superusuario)
        cancelar = self.client.post(
            f'{self.api}/suscripciones/{suscripcion.pk}/cancelar/',
        )
        self.assertEqual(cancelar.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.director_a)
        response = self.client.get('/api/institucion/colegios/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_modulo_no_habilitado_bloquea_en_backend(self):
        suscripcion = self._contratar(self.plan_restringido, self.colegio_a)
        self._activar(suscripcion)
        self.client.force_authenticate(self.director_a)
        bloqueado = self.client.get('/api/institucion/unidades-educativas/')
        self.assertEqual(bloqueado.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('no está habilitado', str(bloqueado.data))
        permitido = self.client.get('/api/institucion/colegios/')
        self.assertEqual(permitido.status_code, status.HTTP_200_OK)

    def test_mi_estado_refleja_suscripcion_pendiente(self):
        self._contratar(self.plan_basico, self.colegio_a)
        self.client.force_authenticate(self.director_a)
        response = self.client.get(f'{self.api}/suscripciones/mi-estado/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertTrue(data['tiene_suscripcion'])
        self.assertEqual(data['plan'], self.plan_basico.nombre)
        self.assertEqual(data['estado'], 'PENDIENTE')
        self.assertFalse(data['suscripcion_activa'])
        self.assertIsNotNone(data['restriccion'])


class LimitesDelPlanTests(BaseSuscripcionesTests):
    def test_limite_usuarios_bloquea_alta(self):
        self._suscripcion_activa_orm(self.colegio_a, limite_usuarios=2)
        self.client.force_authenticate(self.director_a)
        response = self.client.post(
            '/api/usuarios/usuarios/',
            {
                'ci': 'SAAS-NUEVO1', 'username': 'saas_nuevo1',
                'email': 'nuevo1@example.com', 'nombre': 'Nuevo',
                'apellido': 'Usuario', 'sexo': 'M', 'password': self.password,
                'rol_id': self.rol_profesor.pk, 'unidad_id': self.unidad_a.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('límite', str(response.data))
        self.assertFalse(
            Usuario.objects.filter(ci='SAAS-NUEVO1').exists(),
        )

    def test_limite_unidades_bloquea_alta(self):
        self._suscripcion_activa_orm(self.colegio_a, limite_unidades=1)
        crear, _ = Accion.objects.get_or_create(nombre='crear')
        m_unidad, _ = ModeloPermitido.objects.get_or_create(nombre='unidad-educativa')
        PermisoPuesto.objects.get_or_create(
            puesto=self.puesto_director, modelo=m_unidad, accion=crear,
        )
        self.client.force_authenticate(self.director_a)
        response = self.client.post(
            '/api/institucion/unidades-educativas/',
            {
                'codigo_sie': 'SaaS-A2', 'turno': 'TARDE', 'nombre': 'Otra unidad',
                'colegio_id': self.colegio_a.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('límite', str(response.data))
        self.assertFalse(
            UnidadEducativa.objects.filter(codigo_sie='SaaS-A2').exists(),
        )

    def test_limite_cero_no_restringe_altas(self):
        self._suscripcion_activa_orm(
            self.colegio_a, limite_usuarios=0, limite_unidades=0,
        )
        self.client.force_authenticate(self.director_a)
        response = self.client.post(
            '/api/usuarios/usuarios/',
            {
                'ci': 'SAAS-NUEVO2', 'username': 'saas_nuevo2',
                'email': 'nuevo2@example.com', 'nombre': 'Otro',
                'apellido': 'Usuario', 'sexo': 'M', 'password': self.password,
                'rol_id': self.rol_profesor.pk, 'unidad_id': self.unidad_a.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(Usuario.objects.filter(ci='SAAS-NUEVO2').exists())


class AuditoriaYBitacoraTests(BaseSuscripcionesTests):
    def test_contratacion_pago_y_activacion_dejan_rastro(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self._activar(suscripcion)

        self.assertTrue(
            EventoAuditoria.objects.filter(
                entidad='SUSCRIPCION', accion='CREAR', colegio=self.colegio_a,
            ).exists(),
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                entidad='PAGO', accion='CREAR', colegio=self.colegio_a,
            ).exists(),
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                entidad='SUSCRIPCION', accion='ACTUALIZAR', colegio=self.colegio_a,
            ).exists(),
        )
        self.assertTrue(
            Bitacora.objects.filter(
                tabla_afectada='suscripcion', usuario=self.superusuario,
            ).exists(),
        )
        self.assertTrue(
            Bitacora.objects.filter(
                tabla_afectada='pago', usuario=self.superusuario,
            ).exists(),
        )

    def test_validacion_de_pago_tambien_deja_rastro(self):
        suscripcion = self._contratar(self.plan_basico, self.colegio_a)
        self.client.force_authenticate(self.superusuario)
        crear = self.client.post(
            f'{self.api}/pagos/',
            {
                'suscripcion': suscripcion.pk, 'metodo': 'TRANSFERENCIA',
                'referencia': 'TRX-AUD', 'monto': '100.00',
            },
            format='json',
        )
        validar = self.client.post(f'{self.api}/pagos/{crear.data["id"]}/validar/')
        self.assertEqual(validar.status_code, status.HTTP_200_OK)
        self.assertTrue(
            EventoAuditoria.objects.filter(
                entidad='PAGO', accion='ACTUALIZAR', colegio=self.colegio_a,
            ).exists(),
        )
        self.assertTrue(
            Bitacora.objects.filter(
                tabla_afectada='pago', accion='editar',
                usuario=self.superusuario,
            ).exists(),
        )


class AislamientoTenantTests(BaseSuscripcionesTests):
    def test_colegio_no_ve_suscripciones_de_otro_colegio(self):
        sus_a = self._contratar(self.plan_basico, self.colegio_a)
        sus_b = self._contratar(self.plan_restringido, self.colegio_b)

        self.client.force_authenticate(self.director_a)
        lista = self.client.get(f'{self.api}/suscripciones/')
        self.assertEqual(lista.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in lista.data], [sus_a.pk])
        self.assertNotIn(sus_b.pk, [item['id'] for item in lista.data])

        detalle = self.client.get(f'{self.api}/suscripciones/{sus_b.pk}/')
        self.assertEqual(detalle.status_code, status.HTTP_404_NOT_FOUND)

    def test_no_edita_ni_elimina_suscripcion_de_otro_colegio(self):
        self._contratar(self.plan_basico, self.colegio_a)
        sus_b = self._contratar(self.plan_restringido, self.colegio_b)
        self.client.force_authenticate(self.director_a)
        editar = self.client.patch(
            f'{self.api}/suscripciones/{sus_b.pk}/',
            {'estado': Suscripcion.Estado.CANCELADA}, format='json',
        )
        self.assertEqual(editar.status_code, status.HTTP_403_FORBIDDEN)
        borrar = self.client.delete(f'{self.api}/suscripciones/{sus_b.pk}/')
        self.assertEqual(borrar.status_code, status.HTTP_403_FORBIDDEN)
        sus_b.refresh_from_db()
        self.assertEqual(sus_b.estado, Suscripcion.Estado.PENDIENTE)

    def test_pagos_estan_aislados_por_colegio(self):
        sus_a = self._contratar(self.plan_basico, self.colegio_a)
        sus_b = self._contratar(self.plan_restringido, self.colegio_b)
        self._activar(sus_a)
        pago_b = self._activar(sus_b)

        self.client.force_authenticate(self.director_a)
        lista = self.client.get(f'{self.api}/pagos/')
        self.assertEqual(lista.status_code, status.HTTP_200_OK)
        self.assertNotIn(pago_b.pk, [item['id'] for item in lista.data])
        detalle = self.client.get(f'{self.api}/pagos/{pago_b.pk}/')
        self.assertEqual(detalle.status_code, status.HTTP_404_NOT_FOUND)

    def test_mi_estado_solo_del_propio_colegio(self):
        sus_a = self._contratar(self.plan_basico, self.colegio_a)
        sus_b = self._contratar(self.plan_restringido, self.colegio_b)
        self.client.force_authenticate(self.director_a)
        response = self.client.get(f'{self.api}/suscripciones/mi-estado/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['suscripcion'], sus_a.pk)
        self.assertNotEqual(response.data['suscripcion'], sus_b.pk)
        self.assertEqual(response.data['plan'], self.plan_basico.nombre)

    def test_superadmin_ve_todos_los_colegios(self):
        sus_a = self._contratar(self.plan_basico, self.colegio_a)
        sus_b = self._contratar(self.plan_restringido, self.colegio_b)
        self.client.force_authenticate(self.superusuario)
        lista = self.client.get(f'{self.api}/suscripciones/')
        self.assertEqual(
            {item['id'] for item in lista.data}, {sus_a.pk, sus_b.pk},
        )
        filtrada = self.client.get(
            f'{self.api}/suscripciones/?colegio={self.colegio_b.pk}',
        )
        self.assertEqual([item['id'] for item in filtrada.data], [sus_b.pk])

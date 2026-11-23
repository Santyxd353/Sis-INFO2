from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from aplicaciones.estudiantes.models import Estudiante, HistorialInscripcion
from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import Admin, Puesto, Rol, Usuario

from .models import (
    ActividadEvaluacion, AsignacionDocente, Calificacion, Curso,
    DimensionEvaluacion, Grado, Materia, MateriaCurso, Paralelo,
    ResultadoAnual, ResultadoTrimestral,
)
from .resultados import calcular_resultado_trimestral


class EvaluacionHU16HU17Tests(APITestCase):
    url_actividades = '/api/academico/actividades-evaluacion/'
    url_calificaciones = '/api/academico/calificaciones/'
    password = 'Clave-Segura-123'

    @classmethod
    def setUpTestData(cls):
        cls.colegio = Colegio.objects.create(nombre='Colegio HU16', direccion='A', telefono='1')
        cls.unidad = UnidadEducativa.objects.create(
            codigo_sie='HU16-UA', turno='TARDE', nombre='HU16-UA', colegio=cls.colegio,
        )
        cls.grado = Grado.objects.create(unidad_educativa=cls.unidad, nivel_educativo='PRI', numero=3)
        cls.paralelo = Paralelo.objects.create(grado=cls.grado, letra='A')
        cls.curso = Curso.objects.create(paralelo=cls.paralelo, nombre='3ro A')
        cls.materia = Materia.objects.create(nombre='Matemática HU16')
        cls.materia_curso = MateriaCurso.objects.create(curso=cls.curso, materia=cls.materia)

        # Dispara la señal de HU-15: siembra ConfiguracionEvaluacion + 5 dimensiones oficiales.
        cls.gestion = CalendarioAcademico.objects.create(
            unidad_educativa=cls.unidad, año=2026, fecha_inicio=date(2026, 2, 1),
            fecha_fin=date(2026, 11, 30), activo=True,
        )
        cls.periodo = Periodo.objects.create(
            calendario=cls.gestion, tipo_division='TRI', nombre='Trimestre 1',
            fecha_inicio=date(2026, 2, 1), fecha_fin=date(2026, 5, 31), estado='CUR',
        )
        cls.dim_saber = DimensionEvaluacion.objects.get(
            configuracion__calendario_academico=cls.gestion,
            configuracion__nivel='PRI', codigo='SABER',
        )
        cls.dim_hacer = DimensionEvaluacion.objects.get(
            configuracion__calendario_academico=cls.gestion,
            configuracion__nivel='PRI', codigo='HACER',
        )

        rol_profesor, _ = Rol.objects.get_or_create(nombre='Profesor')
        rol_admin, _ = Rol.objects.get_or_create(nombre='Admin')
        rol_estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante')

        cls.superusuario = Usuario.objects.create_superuser(
            ci='HU16-SUP', email='hu16-sup@example.com', nombre='Super', apellido='HU16',
            username='hu16_sup', fecha_nacimiento='1990-01-01', password=cls.password,
        )
        cls.profesor_usuario = Usuario.objects.create_user(
            ci='HU16-PRF', email='hu16-prf@example.com', nombre='Prof', apellido='HU16',
            username='hu16_prf', fecha_nacimiento='1985-01-01', password=cls.password,
            rol=rol_profesor, unidad=cls.unidad,
        )
        cls.profesor = Profesor.objects.create(usuario=cls.profesor_usuario, unidad=cls.unidad)

        cls.otro_profesor_usuario = Usuario.objects.create_user(
            ci='HU16-PRF2', email='hu16-prf2@example.com', nombre='Otro', apellido='HU16',
            username='hu16_prf2', fecha_nacimiento='1985-01-01', password=cls.password,
            rol=rol_profesor, unidad=cls.unidad,
        )
        cls.otro_profesor = Profesor.objects.create(usuario=cls.otro_profesor_usuario, unidad=cls.unidad)

        admin_usuario = Usuario.objects.create_user(
            ci='HU16-DIR', email='hu16-dir@example.com', nombre='Dir', apellido='HU16',
            username='hu16_dir', fecha_nacimiento='1980-01-01', password=cls.password,
            rol=rol_admin, unidad=cls.unidad,
        )
        puesto, _ = Puesto.objects.get_or_create(nombre='Director')
        Admin.objects.create(usuario=admin_usuario, unidad=cls.unidad, puesto=puesto)
        cls.director = admin_usuario

        cls.asignacion = AsignacionDocente.objects.create(
            tipo='MATERIA', calendario_academico=cls.gestion, curso=cls.curso,
            materia_curso=cls.materia_curso, profesor=cls.profesor, fecha_inicio=date(2026, 2, 10),
        )
        cls.asignacion_tutor = AsignacionDocente.objects.create(
            tipo='TUTOR_CURSO', calendario_academico=cls.gestion, curso=cls.curso,
            profesor=cls.profesor, fecha_inicio=date(2026, 2, 10),
        )

        estudiante_usuario = Usuario.objects.create_user(
            ci='HU16-EST', email='hu16-est@example.com', nombre='Est', apellido='HU16',
            username='hu16_est', fecha_nacimiento='2015-01-01', password=cls.password,
            rol=rol_estudiante, unidad=cls.unidad,
        )
        cls.estudiante = Estudiante.objects.create(
            usuario=estudiante_usuario, rude='HU16-RUDE-1', curso=cls.curso, unidad=cls.unidad,
        )
        cls.historial = HistorialInscripcion.objects.create(
            estudiante=cls.estudiante, curso_nuevo=cls.curso, unidad=cls.unidad, tipo_movimiento='NUEVA',
        )

    @classmethod
    def _actividad(cls, dimension, puntaje_maximo=Decimal('100'), asignacion=None):
        return ActividadEvaluacion.objects.create(
            asignacion_docente=asignacion or cls.asignacion, periodo=cls.periodo, dimension=dimension,
            nombre=f'Actividad {dimension.codigo}', fecha=date(2026, 3, 1), puntaje_maximo=puntaje_maximo,
        )

    def autenticar(self, usuario=None):
        self.client.force_authenticate(usuario or self.superusuario)

    # --- HU-16: reglas de negocio sobre actividades/calificaciones ---

    def test_no_se_puede_crear_actividad_sobre_tutoria_de_curso(self):
        self.autenticar(self.profesor_usuario)
        response = self.client.post(self.url_actividades, {
            'asignacion_docente': self.asignacion_tutor.pk, 'periodo': self.periodo.pk,
            'dimension': self.dim_saber.pk, 'nombre': 'Examen', 'fecha': '2026-03-01',
            'puntaje_maximo': '100',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('asignacion_docente', response.data)

    def test_profesor_no_puede_crear_actividad_de_otra_asignacion(self):
        asignacion_otro = AsignacionDocente.objects.create(
            tipo='MATERIA', calendario_academico=self.gestion, curso=self.curso,
            materia_curso=self.materia_curso, profesor=self.otro_profesor, fecha_inicio=date(2026, 2, 10),
        )
        self.autenticar(self.profesor_usuario)
        response = self.client.post(self.url_actividades, {
            'asignacion_docente': asignacion_otro.pk, 'periodo': self.periodo.pk,
            'dimension': self.dim_saber.pk, 'nombre': 'Examen', 'fecha': '2026-03-01',
            'puntaje_maximo': '100',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('asignacion_docente', response.data)

    def test_calificacion_no_puede_superar_puntaje_maximo(self):
        actividad = self._actividad(self.dim_saber, puntaje_maximo=Decimal('50'))
        self.autenticar(self.profesor_usuario)
        response = self.client.post(self.url_calificaciones, {
            'actividad': actividad.pk, 'historial_inscripcion': self.historial.pk, 'valor': '60',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_admin_no_puede_crear_calificaciones_solo_lectura(self):
        actividad = self._actividad(self.dim_saber)
        self.autenticar(self.director)
        response = self.client.post(self.url_calificaciones, {
            'actividad': actividad.pk, 'historial_inscripcion': self.historial.pk, 'valor': '50',
        }, format='json')
        self.assertEqual(response.status_code, 403)

    def test_admin_puede_listar_calificaciones_de_su_unidad(self):
        actividad = self._actividad(self.dim_saber)
        Calificacion.objects.create(actividad=actividad, historial_inscripcion=self.historial, valor=Decimal('50'))
        self.autenticar(self.director)
        response = self.client.get(self.url_calificaciones)
        self.assertEqual(response.status_code, 200)

    def test_carga_masiva_de_calificaciones(self):
        actividad = self._actividad(self.dim_saber, puntaje_maximo=Decimal('100'))
        self.autenticar(self.profesor_usuario)
        response = self.client.put(
            f'{self.url_actividades}{actividad.pk}/calificaciones/',
            {'calificaciones': [{'historial_inscripcion': self.historial.pk, 'valor': '80'}]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Calificacion.objects.get(actividad=actividad, historial_inscripcion=self.historial).valor,
            Decimal('80.00'),
        )

    # --- HU-17: cálculo de promedios ---

    def test_calculo_de_promedio_trimestral_por_dimension_y_redondeo_normal(self):
        # SABER: 2 actividades de 50 pts, nota 40 y 30 -> 70/100 * 35 = 24.5
        act_saber_1 = self._actividad(self.dim_saber, puntaje_maximo=Decimal('50'))
        act_saber_2 = self._actividad(self.dim_saber, puntaje_maximo=Decimal('50'))
        Calificacion.objects.create(actividad=act_saber_1, historial_inscripcion=self.historial, valor=Decimal('40'))
        Calificacion.objects.create(actividad=act_saber_2, historial_inscripcion=self.historial, valor=Decimal('30'))
        # HACER: 1 actividad de 100 pts, nota 100 -> 100/100 * 35 = 35
        act_hacer = self._actividad(self.dim_hacer, puntaje_maximo=Decimal('100'))
        calificacion = Calificacion.objects.create(
            actividad=act_hacer, historial_inscripcion=self.historial, valor=Decimal('100'),
        )
        # Las demás dimensiones (Ser, Decidir, Autoevaluación) sin actividades -> aportan 0.
        # Total = 24.5 + 35 = 59.5 -> redondeo normal (>=0.5 sube) = 60.

        resultado = calcular_resultado_trimestral(self.historial, self.materia, self.periodo)
        self.assertEqual(resultado.resultado, Decimal('60'))
        self.assertEqual(resultado.condicion, 'APROBADO')

        # También se debe recalcular automáticamente al guardar una calificación:
        # al anular HACER, el total baja a 24.5 (solo aporta SABER) -> redondeo
        # normal (>=0.5 sube) = 25, por debajo de la nota de aprobación (51).
        calificacion.valor = Decimal('0')
        calificacion.save()
        from .resultados import recalcular_por_calificacion
        recalcular_por_calificacion(calificacion)
        resultado.refresh_from_db()
        self.assertEqual(resultado.resultado, Decimal('25'))
        self.assertEqual(resultado.condicion, 'REPROBADO')

    def test_resultado_anual_es_promedio_de_trimestrales(self):
        periodo_2 = Periodo.objects.create(
            calendario=self.gestion, tipo_division='TRI', nombre='Trimestre 2',
            fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 8, 31), estado='PLA',
        )
        act_1 = self._actividad(self.dim_saber, puntaje_maximo=Decimal('100'))
        Calificacion.objects.create(actividad=act_1, historial_inscripcion=self.historial, valor=Decimal('100'))
        calcular_resultado_trimestral(self.historial, self.materia, self.periodo)

        act_2 = ActividadEvaluacion.objects.create(
            asignacion_docente=self.asignacion, periodo=periodo_2, dimension=self.dim_saber,
            nombre='Actividad T2', fecha=date(2026, 6, 10), puntaje_maximo=Decimal('100'),
        )
        Calificacion.objects.create(actividad=act_2, historial_inscripcion=self.historial, valor=Decimal('0'))
        calcular_resultado_trimestral(self.historial, self.materia, periodo_2)

        anual = ResultadoAnual.objects.get(historial_inscripcion=self.historial, materia=self.materia)
        trimestrales = list(ResultadoTrimestral.objects.filter(
            historial_inscripcion=self.historial, materia=self.materia,
        ).order_by('periodo__fecha_inicio'))
        # T1 = 35 (100/100*35), T2 = 0 (0/100*35) -> promedio crudo 17.5.
        # El anual se guarda con el mismo redondeo oficial que el trimestral
        # (HU-15: NORMAL, 0 decimales), así que 17.5 sube a 18.
        promedio_crudo = (trimestrales[0].resultado + trimestrales[1].resultado) / 2
        self.assertEqual(promedio_crudo, Decimal('17.50'))
        self.assertEqual(anual.resultado, Decimal('18'))

    def test_anonimo_no_puede_acceder(self):
        response = self.client.get(self.url_actividades)
        self.assertEqual(response.status_code, 401)

    def test_grilla_incluye_resultado_trimestral(self):
        actividad = self._actividad(self.dim_saber, puntaje_maximo=Decimal('100'))
        Calificacion.objects.create(actividad=actividad, historial_inscripcion=self.historial, valor=Decimal('100'))
        calcular_resultado_trimestral(self.historial, self.materia, self.periodo)

        self.autenticar(self.profesor_usuario)
        response = self.client.get(
            f'{self.url_actividades}grilla/',
            {'asignacion_docente': self.asignacion.pk, 'periodo': self.periodo.pk},
        )
        self.assertEqual(response.status_code, 200)
        fila = next(f for f in response.data['estudiantes'] if f['estudiante'] == self.estudiante.pk)
        self.assertIsNotNone(fila['resultado_trimestral'])
        self.assertEqual(fila['historial_inscripcion'], self.historial.pk)
        self.assertEqual(fila['notas'][actividad.pk], '100.00')

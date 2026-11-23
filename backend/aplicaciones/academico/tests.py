from datetime import date, time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from aplicaciones.institucion.models import Aula, Colegio, Modulo, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import Rol, Usuario
from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from aplicaciones.estudiantes.models import Estudiante, HistorialInscripcion
from django.utils import timezone

from .models import (
    AsignacionDocente,
    BloqueHorario,
    Curso,
    Grado,
    HorarioClase,
    Materia,
    MateriaCurso,
    Paralelo,
    ConfiguracionEvaluacion,
    DimensionEvaluacion,
    ActividadEvaluacion,
    Calificacion,
    CorreccionCalificacion,
    ResultadoTrimestral,
    ResultadoAnual,
)


class Sprint2Bloque1AcademicoTests(TestCase):
    def setUp(self):
        self.colegio = Colegio.objects.create(
            nombre='Colegio académico', direccion='Local', telefono='70000001',
        )
        self.unidad = UnidadEducativa.objects.create(
            colegio=self.colegio, codigo_sie='SIE-ACADEMICO', turno='TARDE',
            nombre='Unidad académica',
        )
        grado = Grado.objects.create(
            unidad_educativa=self.unidad, nivel_educativo='PRI', numero=1,
        )
        paralelo = Paralelo.objects.create(grado=grado, letra='Z')
        self.curso = Curso.objects.create(paralelo=paralelo, nombre='Primero Z')
        materia = Materia.objects.create(nombre='Materia Sprint 2')
        self.materia_curso = MateriaCurso.objects.create(curso=self.curso, materia=materia)
        rol, _ = Rol.objects.get_or_create(nombre='Profesor Sprint 2')
        usuario = Usuario.objects.create_user(
            ci='PROF-S2-01', email='prof-s2@example.com', nombre='Docente',
            apellido='Sprint', password='Temporal-123', username='prof_s2',
            fecha_nacimiento='1990-01-01', rol=rol, unidad=self.unidad,
        )
        self.profesor = Profesor.objects.create(usuario=usuario, unidad=self.unidad)
        modulo = Modulo.objects.create(
            nombre='Módulo Sprint 2', cantidad_aulas=1, colegio_fk=self.colegio,
        )
        self.aula = Aula.objects.create(modulo=modulo, nombre='Aula S2', capacidad=30)

    def test_asignacion_docente_valida_tipo_y_unicidad(self):
        asignacion = AsignacionDocente(
            tipo='MATERIA', curso=self.curso, materia_curso=self.materia_curso,
            profesor=self.profesor, fecha_inicio=date(2026, 2, 1), horas_semanales=4,
        )
        asignacion.full_clean()
        asignacion.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            AsignacionDocente.objects.create(
                tipo='MATERIA', curso=self.curso, profesor=self.profesor,
                fecha_inicio=date(2026, 2, 1),
            )

        AsignacionDocente.objects.create(
            tipo='TUTOR_CURSO', curso=self.curso, profesor=self.profesor,
            fecha_inicio=date(2026, 2, 1),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AsignacionDocente.objects.create(
                tipo='TUTOR_CURSO', curso=self.curso, profesor=self.profesor,
                fecha_inicio=date(2026, 2, 2),
            )

    def test_bloque_y_horario_clase_validos(self):
        bloque = BloqueHorario.objects.create(
            unidad_educativa=self.unidad, turno='TARDE', dia=1, orden=1,
            hora_inicio=time(14, 0), hora_fin=time(14, 45),
        )
        bloque_invalido = BloqueHorario(
            unidad_educativa=self.unidad, turno='TARDE', dia=8, orden=2,
            hora_inicio=time(15, 0), hora_fin=time(14, 0),
        )
        with self.assertRaises(ValidationError):
            bloque_invalido.full_clean()

        asignacion = AsignacionDocente.objects.create(
            tipo='MATERIA', curso=self.curso, materia_curso=self.materia_curso,
            profesor=self.profesor, fecha_inicio=date(2026, 2, 1),
        )
        horario = HorarioClase(
            asignacion_docente=asignacion, profesor=self.profesor, curso=self.curso,
            aula=self.aula, bloque_horario=bloque, fecha_inicio=date(2026, 2, 1),
        )
        horario.full_clean()
        horario.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            HorarioClase.objects.create(
                asignacion_docente=asignacion, profesor=self.profesor, curso=self.curso,
                aula=self.aula, bloque_horario=bloque, fecha_inicio=date(2026, 2, 1),
            )


class Sprint2Bloque2EvaluacionTests(TestCase):
    def setUp(self):
        self.colegio = Colegio.objects.create(nombre='Colegio evaluación', direccion='Local', telefono='70000010')
        self.unidad = UnidadEducativa.objects.create(colegio=self.colegio, codigo_sie='SIE-EVAL', turno='TARDE', nombre='Unidad evaluación')
        grado = Grado.objects.create(unidad_educativa=self.unidad, nivel_educativo='PRI', numero=3)
        paralelo = Paralelo.objects.create(grado=grado, letra='X')
        self.curso = Curso.objects.create(paralelo=paralelo, nombre='Tercero X')
        self.materia = Materia.objects.create(nombre='Materia Evaluación')
        self.materia_curso = MateriaCurso.objects.create(curso=self.curso, materia=self.materia)
        rol, _ = Rol.objects.get_or_create(nombre='Rol Evaluación')
        self.usuario = Usuario.objects.create_user(ci='EVAL-USER', email='eval@example.com', nombre='Eva', apellido='Luador', password='Temporal-123', username='eval_user', fecha_nacimiento='1990-01-01', rol=rol, unidad=self.unidad)
        self.profesor = Profesor.objects.create(usuario=self.usuario, unidad=self.unidad)
        self.asignacion = AsignacionDocente.objects.create(tipo='MATERIA', curso=self.curso, materia_curso=self.materia_curso, profesor=self.profesor, fecha_inicio=date(2026, 2, 1))
        self.calendario = CalendarioAcademico.objects.create(unidad_educativa=self.unidad, año=2027, fecha_inicio=date(2027, 2, 1), fecha_fin=date(2027, 11, 30))
        self.periodo = Periodo.objects.create(calendario=self.calendario, tipo_division='TRI', nombre='Primer trimestre', fecha_inicio=date(2027, 2, 1), fecha_fin=date(2027, 5, 1))
        self.configuracion = ConfiguracionEvaluacion.objects.get(calendario_academico=self.calendario, nivel='PRI')
        self.configuracion.decimales = 2
        self.configuracion.save(update_fields=['decimales'])
        self.dimension = DimensionEvaluacion.objects.get(configuracion=self.configuracion, codigo='SER')
        self.actividad = ActividadEvaluacion.objects.create(asignacion_docente=self.asignacion, periodo=self.periodo, dimension=self.dimension, nombre='Actividad', fecha=date(2027, 3, 1), puntaje_maximo=100)
        estudiante_usuario = Usuario.objects.create_user(ci='EVAL-EST', email='eval-est@example.com', nombre='Estudiante', apellido='Eval', password='Temporal-123', username='eval_est', fecha_nacimiento='2015-01-01', rol=rol, unidad=self.unidad)
        estudiante = Estudiante.objects.create(usuario=estudiante_usuario, rude='RUDE-EVAL', curso=self.curso, unidad=self.unidad)
        self.historial = HistorialInscripcion.objects.create(estudiante=estudiante, curso_nuevo=self.curso, unidad=self.unidad, usuario_registra=self.usuario)

    def test_configuracion_evaluacion_rangos(self):
        self.assertEqual(self.configuracion.decimales, 2)
        invalida = ConfiguracionEvaluacion(calendario_academico=self.calendario, nivel='SEC', nota_minima=100, nota_maxima=50, nota_aprobacion=40, decimales=5, regla_redondeo='NORMAL')
        with self.assertRaises(ValidationError):
            invalida.full_clean()

    def test_dimension_ponderacion_y_unicidad(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            DimensionEvaluacion.objects.create(configuracion=self.configuracion, codigo='SER', nombre='Duplicada', ponderacion=20, orden=2)
        invalida = DimensionEvaluacion(configuracion=self.configuracion, codigo='NO', nombre='Inválida', ponderacion=0, orden=0)
        with self.assertRaises(ValidationError):
            invalida.full_clean()

    def test_actividad_coherencia_academica(self):
        self.actividad.full_clean()
        self.assertEqual(self.actividad.estado, 'ACTIVO')
        self.assertEqual(self.actividad.periodo.calendario, self.configuracion.calendario_academico)

    def test_calificacion_unica_y_limite(self):
        calificacion = Calificacion(actividad=self.actividad, historial_inscripcion=self.historial, valor=80)
        calificacion.full_clean(); calificacion.save()
        excesiva = Calificacion(actividad=self.actividad, historial_inscripcion=self.historial, valor=101)
        with self.assertRaises(ValidationError):
            excesiva.full_clean(exclude=['actividad', 'historial_inscripcion'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Calificacion.objects.create(actividad=self.actividad, historial_inscripcion=self.historial, valor=70)

    def test_correccion_flujo_autorizacion(self):
        calificacion = Calificacion.objects.create(actividad=self.actividad, historial_inscripcion=self.historial, valor=70)
        correccion = CorreccionCalificacion.objects.create(calificacion=calificacion, valor_anterior=70, valor_nuevo=80, motivo='Revisión')
        self.assertEqual(correccion.estado, 'SOLICITADA')
        with self.assertRaises(IntegrityError), transaction.atomic():
            CorreccionCalificacion.objects.create(calificacion=calificacion, valor_anterior=70, valor_nuevo=75, motivo='Otra')

    def test_resultado_trimestral(self):
        resultado = ResultadoTrimestral(historial_inscripcion=self.historial, materia=self.materia, periodo=self.periodo, resultado=75, condicion='APROBADO', calculado_at=timezone.now())
        resultado.full_clean(); resultado.save()
        self.assertEqual(resultado.estado, 'CALCULADO')

    def test_resultado_anual(self):
        resultado = ResultadoAnual(historial_inscripcion=self.historial, materia=self.materia, resultado=78, condicion='APROBADO', calculado_at=timezone.now())
        resultado.full_clean(); resultado.save()
        self.assertEqual(resultado.materia, self.materia)

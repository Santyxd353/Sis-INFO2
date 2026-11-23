"""Synthetic school data shared by HU-14/HU-18 tests only."""
from datetime import date
from aplicaciones.usuarios.models import Usuario, Rol, Puesto, Admin, Accion, ModeloPermitido, PermisoPuesto, PermisoRol
from aplicaciones.institucion.models import Colegio, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.estudiantes.models import Estudiante, Tutor, TutorEstudiante, HistorialInscripcion
from aplicaciones.academico.models import Grado, Paralelo, Curso, Materia, MateriaCurso, AsignacionDocente, ConfiguracionEvaluacion, DimensionEvaluacion, ActividadEvaluacion, Calificacion
from aplicaciones.calendario.models import CalendarioAcademico, Periodo


class SchoolFixture:
    @classmethod
    def setUpTestData(cls):
        cls.school = Colegio.objects.create(nombre='HU school', direccion='Test', telefono='0')
        cls.unit = UnidadEducativa.objects.create(colegio=cls.school, codigo_sie='HU-A', turno='TARDE', nombre='Unidad A')
        other = Colegio.objects.create(nombre='Other', direccion='Test', telefono='0')
        cls.other_unit = UnidadEducativa.objects.create(colegio=other, codigo_sie='HU-B', turno='TARDE', nombre='Unidad B')
        def user(name, role, unit=None):
            rol, _ = Rol.objects.get_or_create(nombre=role)
            return Usuario.objects.create_user(ci=name, email=f'{name}@example.com', nombre=name, apellido='Test', username=name, fecha_nacimiento='1990-01-01', rol=rol, unidad=unit or cls.unit)
        cls.teacher = user('teacher', 'Profesor')
        cls.prof = Profesor.objects.create(usuario=cls.teacher, unidad=cls.unit)
        cls.other_teacher = user('other_teacher', 'Profesor')
        Profesor.objects.create(usuario=cls.other_teacher, unidad=cls.unit)
        cls.director = user('director', 'Admin')
        cls.regent = user('regent', 'Admin')
        cls.outsider = user('outsider', 'Admin', cls.other_unit)
        for u, title in ((cls.director, 'Director'), (cls.regent, 'Regente'), (cls.outsider, 'Director')):
            puesto, _ = Puesto.objects.get_or_create(nombre=title)
            Admin.objects.create(usuario=u, puesto=puesto, unidad=u.unidad, colegio=u.unidad.colegio)
        for name in ('disciplina', 'correccion-nota'):
            model, _ = ModeloPermitido.objects.get_or_create(nombre=name)
            for action in ('listar', 'crear', 'editar'):
                a, _ = Accion.objects.get_or_create(nombre=action)
                for u in (cls.director, cls.regent):
                    if name == 'disciplina' or u == cls.director:
                        PermisoPuesto.objects.get_or_create(puesto=u.admin.puesto, modelo=model, accion=a)
                if name == 'correccion-nota' and action != 'editar':
                    PermisoRol.objects.get_or_create(rol=cls.teacher.rol, modelo=model, accion=a)
        grade = Grado.objects.create(unidad_educativa=cls.unit, nivel_educativo='PRI', numero=3)
        cls.course = Curso.objects.create(paralelo=Paralelo.objects.create(grado=grade, letra='A'), nombre='Tercero A')
        cls.student_user = user('student', 'Estudiante')
        cls.student = Estudiante.objects.create(usuario=cls.student_user, rude='HU-RUDE', curso=cls.course, unidad=cls.unit)
        cls.enrollment = HistorialInscripcion.objects.create(estudiante=cls.student, curso_nuevo=cls.course, unidad=cls.unit)
        cls.tutor_user = user('tutor', 'Tutor')
        cls.tutor = TutorEstudiante.objects.create(estudiante=cls.student, tutor=Tutor.objects.create(usuario=cls.tutor_user))
        cls.calendar = CalendarioAcademico.objects.create(unidad_educativa=cls.unit, año=2026, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31))
        cls.period = Periodo.objects.create(calendario=cls.calendar, tipo_division='TRI', nombre='T1', fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 4, 30), estado='FIN')
        cls.subject = Materia.objects.create(nombre='Matemática')
        mc = MateriaCurso.objects.create(curso=cls.course, materia=cls.subject)
        cls.assignment = AsignacionDocente.objects.create(tipo='MATERIA', curso=cls.course, materia_curso=mc, profesor=cls.prof, calendario_academico=cls.calendar, fecha_inicio=date(2026, 1, 1))
        # CalendarioAcademico siembra esta configuración mediante la señal de HU-15.
        # El fixture debe reutilizarla para no duplicar la unicidad calendario+nivel.
        cls.config, _ = ConfiguracionEvaluacion.objects.get_or_create(
            calendario_academico=cls.calendar,
            nivel='PRI',
            defaults={
                'nota_minima': 0, 'nota_maxima': 100,
                'nota_aprobacion': 51, 'regla_redondeo': 'NORMAL',
            },
        )
        cls.dimension, _ = DimensionEvaluacion.objects.get_or_create(
            configuracion=cls.config, codigo='SABER',
            defaults={'nombre': 'Saber', 'ponderacion': 100, 'orden': 1},
        )
        # Este fixture representa una evaluación de una sola dimensión. La
        # señal del calendario crea cinco por defecto; mantenerlas activas
        # exigiría calificaciones que estos escenarios no preparan.
        cls.config.dimensiones.exclude(pk=cls.dimension.pk).update(estado='INACTIVO')
        cls.dimension.ponderacion = 100
        cls.dimension.save(update_fields=['ponderacion'])
        cls.activity = ActividadEvaluacion.objects.create(asignacion_docente=cls.assignment, periodo=cls.period, dimension=cls.dimension, nombre='Examen', fecha=date(2026, 3, 1), puntaje_maximo=100)
        cls.grade = Calificacion.objects.create(actividad=cls.activity, historial_inscripcion=cls.enrollment, valor=60)

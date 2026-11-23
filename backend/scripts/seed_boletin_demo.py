"""Seed de demostración: arma un curso/materia/calificación mínimos para el
usuario 'estudiante' (creado por seed_demo_se02.py) y emite un boletín real
en PDF, disparando la notificación push como lo haría la API.

Requisito: haber corrido antes scripts/seed_demo_se02.py (usa sus usuarios
admin/director/profesor/estudiante/tutor).

Uso:  python scripts/seed_boletin_demo.py
Idempotente: no duplica curso, materia, gestión ni calificación si ya existen.
"""
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django  # noqa: E402

django.setup()

from aplicaciones.academico.models import (  # noqa: E402
    ActividadEvaluacion, AsignacionDocente, Calificacion, Curso, DimensionEvaluacion,
    Grado, Materia, MateriaCurso, Paralelo,
)
from aplicaciones.academico.resultados import calcular_resultado_trimestral  # noqa: E402
from aplicaciones.calendario.models import CalendarioAcademico, Periodo  # noqa: E402
from aplicaciones.estudiantes import boletines  # noqa: E402
from aplicaciones.estudiantes.models import Estudiante, HistorialInscripcion, Tutor, TutorEstudiante  # noqa: E402
from aplicaciones.estudiantes.views import DocumentoAcademicoEmitidoViewSet  # noqa: E402
from aplicaciones.institucion.models import UnidadEducativa  # noqa: E402
from aplicaciones.personal.models import Profesor  # noqa: E402
from aplicaciones.usuarios.models import Usuario  # noqa: E402


def main():
    print('Seed boletín demo')
    unidad = UnidadEducativa.objects.get(codigo_sie='DEMO-SI2-01')
    director = Usuario.objects.get(username='director')
    profesor_usuario = Usuario.objects.get(username='profesor')
    profesor = Profesor.objects.get(usuario=profesor_usuario)
    estudiante_usuario = Usuario.objects.get(username='estudiante')
    estudiante = Estudiante.objects.get(usuario=estudiante_usuario)
    tutor_usuario = Usuario.objects.get(username='tutor')
    tutor = Tutor.objects.get(usuario=tutor_usuario)

    grado, _ = Grado.objects.get_or_create(unidad_educativa=unidad, nivel_educativo='PRI', numero=4)
    paralelo, _ = Paralelo.objects.get_or_create(grado=grado, letra='A')
    curso, _ = Curso.objects.get_or_create(paralelo=paralelo, defaults={'nombre': '4to A Demo'})
    print(f'  = curso: {curso.nombre}')

    materia, _ = Materia.objects.get_or_create(
        nombre='Matemática Demo', unidad_educativa=unidad,
    )
    materia_curso, _ = MateriaCurso.objects.get_or_create(curso=curso, materia=materia, defaults={'profesor': profesor})

    gestion, _ = CalendarioAcademico.objects.get_or_create(
        unidad_educativa=unidad, año=2026,
        defaults={'fecha_inicio': date(2026, 2, 1), 'fecha_fin': date(2026, 11, 30), 'activo': True},
    )
    periodo, _ = Periodo.objects.get_or_create(
        calendario=gestion, tipo_division='TRI', nombre='Trimestre 1',
        defaults={'fecha_inicio': date(2026, 2, 1), 'fecha_fin': date(2026, 5, 31), 'estado': 'CUR'},
    )
    dim_saber = DimensionEvaluacion.objects.get(
        configuracion__calendario_academico=gestion, configuracion__nivel='PRI', codigo='SABER',
    )

    if estudiante.curso_id != curso.pk:
        estudiante.curso = curso
        estudiante.save(update_fields=['curso'])
        print('  + estudiante asignado al curso')

    historial = HistorialInscripcion.objects.filter(estudiante=estudiante, curso_nuevo=curso).first()
    if historial is None:
        historial = HistorialInscripcion.objects.create(
            estudiante=estudiante, curso_nuevo=curso, unidad=unidad, tipo_movimiento='NUEVA',
        )
        print('  + historial de inscripción creado')

    TutorEstudiante.objects.get_or_create(tutor=tutor, estudiante=estudiante, defaults={'es_principal': True})

    asignacion, _ = AsignacionDocente.objects.get_or_create(
        tipo='MATERIA', calendario_academico=gestion, curso=curso, materia_curso=materia_curso,
        profesor=profesor, defaults={'fecha_inicio': date(2026, 2, 10)},
    )
    actividad, _ = ActividadEvaluacion.objects.get_or_create(
        asignacion_docente=asignacion, periodo=periodo, dimension=dim_saber, nombre='Examen Demo',
        defaults={'fecha': date(2026, 3, 1), 'puntaje_maximo': Decimal('100')},
    )
    Calificacion.objects.get_or_create(
        actividad=actividad, historial_inscripcion=historial, defaults={'valor': Decimal('90')},
    )
    calcular_resultado_trimestral(historial, materia, periodo)
    print('  = calificación y resultado trimestral listos')

    documento, _ = boletines.emitir_boletin(historial, gestion, periodo=periodo, usuario=director)
    print(f'  + boletín emitido: id={documento.pk}, version={documento.version}')

    DocumentoAcademicoEmitidoViewSet._notificar_boletin(historial, documento)
    print('  + notificación push disparada (si hay dispositivo activo registrado)')

    print('LISTO.')


if __name__ == '__main__':
    main()

"""HU-19: generación de boletines individuales y centralizadores en PDF.

Boletín = un estudiante, todas sus materias, con el detalle por dimensión
(Ser/Saber/Hacer/Decidir/Autoevaluación) y el resultado ya calculado por
HU-17. Centralizador = un curso, todos sus estudiantes x materias, solo
con el resultado final.

No se modifica ningún modelo: DocumentoAcademicoEmitido ya existía.
"""
import hashlib
import io
import uuid
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Max
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from aplicaciones.academico.models import MateriaCurso, ResultadoAnual, ResultadoTrimestral
from aplicaciones.academico.resultados import desglose_por_dimension, historial_actual

from .models import DocumentoAcademicoEmitido, Estudiante

ESTILOS = getSampleStyleSheet()
ESTILO_TABLA = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),
    ('FONTSIZE', (0, 0), (-1, -1), 8),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
])


def _materias_del_curso(curso):
    return [
        mc.materia for mc in MateriaCurso.objects.filter(curso=curso)
        .select_related('materia').order_by('materia__nombre')
    ]


def _encabezado(curso, titulo, subtitulo):
    unidad = curso.paralelo.grado.unidad_educativa
    colegio = unidad.colegio
    elementos = []
    if colegio and colegio.logo:
        try:
            elementos.append(Image(colegio.logo.path, width=2 * cm, height=2 * cm))
        except (ValueError, OSError):
            pass
    elementos.append(Paragraph(colegio.nombre if colegio else '', ESTILOS['Title']))
    elementos.append(Paragraph(unidad.nombre or '', ESTILOS['Normal']))
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph(titulo, ESTILOS['Heading2']))
    elementos.append(Paragraph(subtitulo, ESTILOS['Normal']))
    elementos.append(Spacer(1, 0.4 * cm))
    return elementos


def generar_boletin_pdf(historial_inscripcion, periodo=None):
    curso = historial_inscripcion.curso_nuevo
    estudiante = historial_inscripcion.estudiante
    materias = _materias_del_curso(curso)
    subtitulo = (
        f'{periodo.nombre} — Gestión {periodo.calendario.año}' if periodo
        else 'Promedio anual'
    )

    cuerpo = _encabezado(
        curso, f'Boletín de calificaciones — {estudiante.usuario.get_full_name()}', subtitulo,
    )
    cuerpo.append(Paragraph(f'RUDE: {estudiante.rude} — Curso: {curso.nombre}', ESTILOS['Normal']))
    cuerpo.append(Spacer(1, 0.4 * cm))

    encabezados = ['Materia']
    dim_codigos = []
    filas = []
    for materia in materias:
        if periodo:
            desglose, _ = desglose_por_dimension(historial_inscripcion, materia, periodo)
            if not dim_codigos:
                dim_codigos = [item['dimension'].codigo for item in desglose]
            fila = [materia.nombre] + [
                str(item['aporte'].quantize(Decimal('0.01'))) for item in desglose
            ]
            resultado = ResultadoTrimestral.objects.filter(
                historial_inscripcion=historial_inscripcion, materia=materia, periodo=periodo,
            ).first()
        else:
            fila = [materia.nombre]
            resultado = ResultadoAnual.objects.filter(
                historial_inscripcion=historial_inscripcion, materia=materia,
            ).first()
        fila.append(str(resultado.resultado) if resultado else '—')
        fila.append(resultado.condicion if resultado else '—')
        filas.append(fila)

    encabezados += dim_codigos + ['Total', 'Condición']
    tabla = Table([encabezados] + filas, hAlign='LEFT')
    tabla.setStyle(ESTILO_TABLA)
    cuerpo.append(tabla)
    cuerpo.append(Spacer(1, 1 * cm))
    cuerpo.append(Paragraph(f'Emitido el {timezone.now():%d/%m/%Y %H:%M}', ESTILOS['Normal']))

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=letter).build(cuerpo)
    return buffer.getvalue()


def generar_centralizador_pdf(curso, periodo=None):
    materias = _materias_del_curso(curso)
    estudiantes = list(
        Estudiante.objects.filter(curso=curso).select_related('usuario')
        .order_by('usuario__apellido', 'usuario__nombre'),
    )
    historiales = {estudiante.pk: historial_actual(estudiante) for estudiante in estudiantes}
    historial_ids = [h.pk for h in historiales.values() if h is not None]

    if periodo:
        resultados_qs = ResultadoTrimestral.objects.filter(
            historial_inscripcion_id__in=historial_ids, materia__in=materias, periodo=periodo,
        )
    else:
        resultados_qs = ResultadoAnual.objects.filter(
            historial_inscripcion_id__in=historial_ids, materia__in=materias,
        )
    resultados = {(r.historial_inscripcion_id, r.materia_id): r for r in resultados_qs}

    subtitulo = f'{periodo.nombre} — Gestión {periodo.calendario.año}' if periodo else 'Promedio anual'
    cuerpo = _encabezado(curso, f'Centralizador — {curso.nombre}', subtitulo)

    encabezados = ['Estudiante'] + [materia.nombre for materia in materias]
    filas = []
    for estudiante in estudiantes:
        historial = historiales[estudiante.pk]
        fila = [str(estudiante.usuario)]
        for materia in materias:
            resultado = resultados.get((historial.pk, materia.pk)) if historial else None
            fila.append(str(resultado.resultado) if resultado else '—')
        filas.append(fila)

    tabla = Table([encabezados] + filas, hAlign='LEFT')
    tabla.setStyle(ESTILO_TABLA)
    cuerpo.append(tabla)
    cuerpo.append(Spacer(1, 1 * cm))
    cuerpo.append(Paragraph(f'Emitido el {timezone.now():%d/%m/%Y %H:%M}', ESTILOS['Normal']))

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=letter).build(cuerpo)
    return buffer.getvalue()


def _guardar_documento(tipo, contenido_pdf, *, historial_inscripcion, curso, periodo, calendario_academico, usuario):
    version = (
        DocumentoAcademicoEmitido.objects.filter(
            tipo=tipo, historial_inscripcion=historial_inscripcion, curso=curso, periodo=periodo,
        ).aggregate(maximo=Max('version'))['maximo'] or 0
    ) + 1
    ruta = default_storage.save(
        f'documentos_academicos/{tipo.lower()}/{uuid.uuid4().hex}_v{version}.pdf',
        ContentFile(contenido_pdf),
    )
    autenticado = usuario is not None and getattr(usuario, 'is_authenticated', False)
    documento = DocumentoAcademicoEmitido.objects.create(
        tipo=tipo, historial_inscripcion=historial_inscripcion, curso=curso, periodo=periodo,
        calendario_academico=calendario_academico, version=version,
        archivo_ref=ruta, archivo_mime='application/pdf',
        archivo_tamano=len(contenido_pdf),
        archivo_checksum=hashlib.sha256(contenido_pdf).hexdigest(),
        emitido_por=usuario if autenticado else None,
        emisor_snapshot=str(usuario) if autenticado else None,
        emitido_at=timezone.now(),
    )
    return documento, ruta


def emitir_boletin(historial_inscripcion, calendario_academico, periodo=None, usuario=None):
    pdf = generar_boletin_pdf(historial_inscripcion, periodo)
    return _guardar_documento(
        DocumentoAcademicoEmitido.Tipo.BOLETIN, pdf,
        historial_inscripcion=historial_inscripcion, curso=None, periodo=periodo,
        calendario_academico=calendario_academico, usuario=usuario,
    )


def emitir_centralizador(curso, calendario_academico, periodo=None, usuario=None):
    pdf = generar_centralizador_pdf(curso, periodo)
    return _guardar_documento(
        DocumentoAcademicoEmitido.Tipo.CENTRALIZADOR, pdf,
        historial_inscripcion=None, curso=curso, periodo=periodo,
        calendario_academico=calendario_academico, usuario=usuario,
    )

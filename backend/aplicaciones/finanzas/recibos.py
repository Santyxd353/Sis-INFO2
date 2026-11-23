import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ESTILOS = getSampleStyleSheet()


def generar_recibo_pdf(pago):
    """Recibo imprimible del pago; un pago anulado se marca como tal."""
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=landscape(A5), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm, title=f'Recibo {pago.numero_recibo}',
    )
    unidad = pago.unidad_educativa
    estudiante = pago.estudiante
    nombre = f'{estudiante.usuario.nombre} {estudiante.usuario.apellido}'.strip()
    contenido = [
        Paragraph(f'<b>{unidad.colegio.nombre if unidad.colegio_id else ""}</b> — {unidad.nombre}', ESTILOS['Normal']),
        Paragraph(f'RECIBO DE PAGO N.º {pago.numero_recibo:06d}', ESTILOS['Title']),
    ]
    if pago.estado == 'ANULADO':
        contenido.append(Paragraph(f'<font color="red"><b>ANULADO</b>: {pago.motivo_anulacion}</font>', ESTILOS['Normal']))
    datos = [
        ['Estudiante', nombre, 'Fecha', pago.fecha_pago.strftime('%d/%m/%Y')],
        ['RUDE', estudiante.rude, 'Método', pago.get_metodo_display()],
        ['Curso', estudiante.curso.nombre if estudiante.curso else '—', 'Referencia', pago.referencia or '—'],
    ]
    contenido += [Spacer(1, 0.3 * cm), Table(datos, colWidths=[2.5 * cm, 7 * cm, 2.5 * cm, 5 * cm])]
    filas = [['Concepto', 'Plan', 'Monto (Bs)']] + [
        [d.obligacion.cuota.concepto, d.obligacion.cuota.plan.nombre, f'{d.monto:,.2f}'] for d in pago.detalles.all()
    ] + [['', 'TOTAL', f'{pago.monto:,.2f}']]
    tabla = Table(filas, colWidths=[7 * cm, 6.5 * cm, 3.5 * cm])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#94a3b8')),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (1, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    registrado = pago.registrado_por
    contenido += [
        Spacer(1, 0.4 * cm), tabla, Spacer(1, 0.6 * cm),
        Paragraph(f'Registrado por: {registrado.nombre} {registrado.apellido}' if registrado else '', ESTILOS['Normal']),
        Paragraph('Este recibo no reemplaza a la factura fiscal.', ESTILOS['Italic']),
    ]
    documento.build(contenido)
    return buffer.getvalue()

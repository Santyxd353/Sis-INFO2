"""Exportaciones efímeras de reportes; no persisten archivos académicos."""
from io import BytesIO
from re import sub

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .csv_seguro import generar_csv


def nombre_seguro(nombre, extension):
    base = sub(r'[^a-z0-9]+', '-', nombre.lower()).strip('-') or 'reporte'
    return f'{base}.{extension}'


def exportar_csv(encabezados, filas):
    return generar_csv(encabezados, filas), 'text/csv; charset=utf-8', 'csv'


def exportar_pdf(titulo, encabezados, filas):
    salida = BytesIO()
    documento = SimpleDocTemplate(salida, pagesize=landscape(letter), title=titulo)
    estilos = getSampleStyleSheet()
    datos = [[Paragraph(str(valor), estilos['BodyText']) for valor in encabezados]]
    for fila in filas:
        datos.append([Paragraph('' if valor is None else str(valor), estilos['BodyText']) for valor in fila])
    tabla = Table(datos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e78')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    documento.build([Paragraph(titulo, estilos['Title']), Spacer(1, 10), tabla])
    return salida.getvalue(), 'application/pdf', 'pdf'

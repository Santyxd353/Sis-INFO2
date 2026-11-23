"""Construcción de CSV sin interpretar contenido como fórmulas de hoja de cálculo."""
import csv
import io
from datetime import date, datetime
from decimal import Decimal


def valor_csv(valor):
    if valor is None:
        return ''
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        return str(valor)
    texto = str(valor)
    # Considerar espacios iniciales evita que la aplicación de destino los descarte
    # y termine interpretando como fórmula un texto aparentemente inocuo.
    if texto.startswith(('=', '+', '-', '@', '\t', '\r')) or texto.lstrip(' ').startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + texto
    return texto


def generar_csv(encabezados, filas):
    """Devuelve bytes UTF-8 con BOM; el llamador controla columnas y filas."""
    salida = io.StringIO(newline='')
    escritor = csv.writer(salida, lineterminator='\r\n')
    escritor.writerow([valor_csv(valor) for valor in encabezados])
    for fila in filas:
        escritor.writerow([valor_csv(valor) for valor in fila])
    return salida.getvalue().encode('utf-8-sig')

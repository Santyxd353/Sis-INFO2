import csv
import io
from datetime import date
from decimal import Decimal
from django.test import SimpleTestCase
from .csv_seguro import generar_csv


class CsvSeguroTests(SimpleTestCase):
    def test_formulas_textuales_se_neutralizan_y_se_preservan_los_numeros(self):
        valores = ['=1+1', '+1', '-1', '@cmd', '\tformula', '\rformula', '  =1', Decimal('-1.25'), None, date(2026, 1, 2)]
        archivo = generar_csv(['Nombre'], [valores])
        self.assertTrue(archivo.startswith(b'\xef\xbb\xbf'))
        filas = list(csv.reader(io.StringIO(archivo.decode('utf-8-sig'), newline='')))
        self.assertEqual(filas[1], ["'" + valor for valor in valores[:7]] + ['-1.25', '', '2026-01-02'])

    def test_caracteres_especiales_csv_se_escapan(self):
        archivo = generar_csv(['Columna'], [['a,b\n"c"']])
        self.assertEqual(list(csv.reader(io.StringIO(archivo.decode('utf-8-sig'), newline='')))[1], ['a,b\n"c"'])

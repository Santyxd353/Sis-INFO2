from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from .especificacion import validar_especificacion


class EspecificacionOperativaTests(SimpleTestCase):
    fuente = {'columnas': {'nombre', 'promedio'}, 'filtros': {'nombre': 'texto', 'promedio': 'decimal', 'fecha': 'fecha'}, 'ordenables': {'nombre'}}

    def test_normaliza_valores_sin_mutar_entrada(self):
        valor = {'columnas': ['nombre'], 'filtros': [{'campo': 'nombre', 'operador': 'eq', 'valor': ' Ana '}], 'orden': [{'campo': 'nombre', 'direccion': 'asc'}]}
        self.assertEqual(validar_especificacion(valor, self.fuente)['filtros'][0]['valor'], 'Ana')
        self.assertEqual(valor['filtros'][0]['valor'], ' Ana ')

    def test_rechaza_campos_sql_rutas_y_estructuras_extras(self):
        for campo in ('nombre__secret', 'SELECT * FROM usuario', 'desconocido'):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                validar_especificacion({'columnas': [campo], 'filtros': [], 'orden': []}, self.fuente)
        with self.assertRaises(ValidationError):
            validar_especificacion({'columnas': ['nombre'], 'filtros': [], 'orden': [], 'sql': 'x'}, self.fuente)

    def test_rechaza_operadores_valores_y_limites(self):
        casos = [
            {'columnas': ['nombre'] * 16, 'filtros': [], 'orden': []},
            {'columnas': ['nombre'], 'filtros': [{'campo': 'nombre', 'operador': 'eq', 'valor': 'x'}] * 11, 'orden': []},
            {'columnas': ['nombre'], 'filtros': [{'campo': 'nombre', 'operador': 'gte', 'valor': 'x'}], 'orden': []},
            {'columnas': ['nombre'], 'filtros': [{'campo': 'promedio', 'operador': 'eq', 'valor': 'NaN'}], 'orden': []},
            {'columnas': ['nombre'], 'filtros': [{'campo': 'fecha', 'operador': 'date_gte', 'valor': '2026-02-31'}], 'orden': []},
            {'columnas': ['nombre'], 'filtros': [], 'orden': [{'campo': 'nombre', 'direccion': 'desc'}] * 4},
        ]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(ValidationError):
                validar_especificacion(caso, self.fuente)

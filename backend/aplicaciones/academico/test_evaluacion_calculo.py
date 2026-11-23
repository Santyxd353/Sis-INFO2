from decimal import Decimal as D
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from importlib import import_module, util


class CalculoTests(SimpleTestCase):
    def calculator(self):
        name = 'aplicaciones.academico.evaluacion_calculo'
        self.assertIsNotNone(util.find_spec(name), 'Falta servicio de cálculo')
        return import_module(name)

    def test_weighted_dimensions(self):
        c = self.calculator()
        dims = [c.DimensionEntrada(D('40'), (c.NotaEntrada(D('8'), D('10'), None),)), c.DimensionEntrada(D('60'), (c.NotaEntrada(D('15'), D('20'), None),))]
        self.assertEqual(c.calcular_trimestre(dims, minimo=D(0), maximo=D(100), decimales=2, redondeo='NORMAL'), D('77.00'))

    def test_activity_weights(self):
        c = self.calculator()
        dims = [c.DimensionEntrada(D(100), (c.NotaEntrada(D(5), D(10), D(25)), c.NotaEntrada(D(10), D(10), D(75))))]
        self.assertEqual(c.calcular_trimestre(dims, minimo=D(0), maximo=D(100), decimales=2, redondeo='NORMAL'), D('87.50'))

    def test_rounding_and_annual(self):
        c = self.calculator()
        for rule, expected in [('NORMAL', '2.35'), ('TRUNCAR', '2.34'), ('SUPERIOR', '2.35')]:
            self.assertEqual(c.calcular_anual((D('2.345'),), decimales=2, redondeo=rule), D(expected))
        self.assertEqual(c.calcular_anual((D(70), D(80), D(90)), decimales=2, redondeo='NORMAL'), D('80.00'))

    def test_invalid_precision_and_missing_values(self):
        c = self.calculator()
        for precision in (3, 4, -1):
            with self.assertRaises(ValidationError):
                c.calcular_anual((D('80'),), decimales=precision, redondeo='NORMAL')
        with self.assertRaises(ValidationError):
            c.calcular_anual((), decimales=2, redondeo='NORMAL')

    def test_invalid_dimensions_and_mixed_weights(self):
        c = self.calculator()
        cases = [[], [c.DimensionEntrada(D(50), ())], [c.DimensionEntrada(D(100), (c.NotaEntrada(D(5), D(10), None), c.NotaEntrada(D(5), D(10), D(50))))], [c.DimensionEntrada(D(100), (c.NotaEntrada(D(11), D(10), None),))]]
        for dims in cases:
            with self.assertRaises(ValidationError):
                c.calcular_trimestre(dims, minimo=D(0), maximo=D(100), decimales=2, redondeo='NORMAL')

"""Decimal-only evaluation arithmetic, independent of persistence."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_CEILING
from rest_framework.exceptions import ValidationError


@dataclass(frozen=True)
class NotaEntrada:
    valor: Decimal
    maximo: Decimal
    peso: Decimal | None


@dataclass(frozen=True)
class DimensionEntrada:
    peso: Decimal
    notas: tuple[NotaEntrada, ...]


def redondear(value, decimales, regla):
    modes = {'NORMAL': ROUND_HALF_UP, 'TRUNCAR': ROUND_DOWN, 'SUPERIOR': ROUND_CEILING}
    if decimales not in (0, 1, 2) or regla not in modes:
        raise ValidationError('Precisión o redondeo incompatible con los resultados (máximo 2 decimales).')
    if not value.is_finite():
        raise ValidationError('Resultado no finito.')
    return value.quantize(Decimal(1).scaleb(-decimales), rounding=modes[regla])


def calcular_trimestre(dimensiones, *, minimo, maximo, decimales, redondeo):
    if not dimensiones or sum(d.peso for d in dimensiones) != Decimal(100):
        raise ValidationError('Las dimensiones activas deben sumar 100%.')
    if not minimo.is_finite() or not maximo.is_finite() or minimo < 0 or maximo <= minimo:
        raise ValidationError('Escala inválida.')
    proportion = Decimal(0)
    for dimension in dimensiones:
        if not dimension.notas or not 0 < dimension.peso <= 100:
            raise ValidationError('Faltan calificaciones en una dimensión activa.')
        weighted = [n.peso is not None for n in dimension.notas]
        if any(weighted) and not all(weighted):
            raise ValidationError('No se pueden mezclar actividades con y sin ponderación.')
        total = weight_sum = Decimal(0)
        for nota in dimension.notas:
            if not nota.valor.is_finite() or not nota.maximo.is_finite() or nota.maximo <= 0 or not 0 <= nota.valor <= nota.maximo:
                raise ValidationError('Calificación fuera del rango de su actividad.')
            weight = nota.peso if all(weighted) else Decimal(1)
            if not weight.is_finite() or weight <= 0 or (all(weighted) and weight > 100):
                raise ValidationError('Ponderación de actividad inválida.')
            total += nota.valor / nota.maximo * weight
            weight_sum += weight
        proportion += total / weight_sum * dimension.peso / Decimal(100)
    return redondear(minimo + proportion * (maximo - minimo), decimales, redondeo)


def calcular_anual(resultados, *, decimales, redondeo):
    if not resultados:
        raise ValidationError('Faltan resultados para el cálculo anual.')
    return redondear(sum(resultados) / Decimal(len(resultados)), decimales, redondeo)

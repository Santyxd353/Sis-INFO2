"""Validación cerrada de especificaciones operativas para fuentes registradas."""
from datetime import date
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from .seguridad import validar_json

OPERADORES = {
    'texto': {'eq', 'in', 'contains'},
    'entero': {'eq', 'in', 'gte', 'lte'},
    'decimal': {'eq', 'in', 'gte', 'lte'},
    'fecha': {'eq', 'in', 'date_gte', 'date_lte'},
    'booleano': {'eq', 'in'},
}


def _valor(valor, tipo):
    try:
        if tipo == 'texto':
            if not isinstance(valor, str) or not valor.strip() or len(valor) > 500:
                raise ValueError
            return valor.strip()
        if tipo == 'entero':
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                raise ValueError
            return valor
        if tipo == 'decimal':
            if isinstance(valor, bool) or not isinstance(valor, (str, int, float)):
                raise ValueError
            numero = Decimal(str(valor))
            if not numero.is_finite():
                raise ValueError
            return str(numero)
        if tipo == 'fecha':
            if not isinstance(valor, str):
                raise ValueError
            return date.fromisoformat(valor).isoformat()
        if tipo == 'booleano' and isinstance(valor, bool):
            return valor
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        pass
    raise ValidationError('Valor incompatible con el filtro.')


def validar_especificacion(especificacion, fuente):
    """Valida contra un esquema interno, sin aceptar rutas de consulta del cliente.

    fuente contiene columnas (colección), filtros (campo -> tipo) y ordenables.
    """
    if not isinstance(especificacion, dict) or set(especificacion) != {'columnas', 'filtros', 'orden'}:
        raise ValidationError('La especificación requiere únicamente columnas, filtros y orden.')
    validar_json(especificacion)
    columnas, filtros, orden = (especificacion[k] for k in ('columnas', 'filtros', 'orden'))
    if not isinstance(columnas, list) or not 1 <= len(columnas) <= 15:
        raise ValidationError('Seleccione entre una y quince columnas.')
    if any(not isinstance(c, str) or c not in fuente['columnas'] for c in columnas) or len(set(columnas)) != len(columnas):
        raise ValidationError('Columnas no permitidas o duplicadas.')
    if not isinstance(filtros, list) or len(filtros) > 10:
        raise ValidationError('Se permiten hasta diez filtros.')
    normalizados = []
    for filtro in filtros:
        if not isinstance(filtro, dict) or set(filtro) != {'campo', 'operador', 'valor'}:
            raise ValidationError('Filtro inválido.')
        campo, operador, valor = filtro['campo'], filtro['operador'], filtro['valor']
        if not isinstance(campo, str) or campo not in fuente['filtros']:
            raise ValidationError('Filtro no permitido.')
        tipo = fuente['filtros'][campo]
        if not isinstance(operador, str) or operador not in OPERADORES.get(tipo, set()):
            raise ValidationError('Operador no permitido.')
        if operador == 'in':
            if not isinstance(valor, list) or not 1 <= len(valor) <= 100:
                raise ValidationError('La lista del filtro debe contener entre uno y cien valores.')
            valor = [_valor(v, tipo) for v in valor]
        else:
            valor = _valor(valor, tipo)
        normalizados.append({'campo': campo, 'operador': operador, 'valor': valor})
    if not isinstance(orden, list) or len(orden) > 3:
        raise ValidationError('Se permiten hasta tres campos de orden.')
    vistos = set()
    for item in orden:
        if not isinstance(item, dict) or set(item) != {'campo', 'direccion'}:
            raise ValidationError('Orden inválido.')
        campo, direccion = item['campo'], item['direccion']
        if not isinstance(campo, str) or campo not in fuente['ordenables'] or campo in vistos or direccion not in ('asc', 'desc'):
            raise ValidationError('Orden no permitido.')
        vistos.add(campo)
    return {'columnas': list(columnas), 'filtros': normalizados, 'orden': list(orden)}

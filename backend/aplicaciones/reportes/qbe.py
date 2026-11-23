"""Constructor QBE cerrado sobre las fuentes operativas aprobadas."""
from django.core.exceptions import ValidationError
from django.db.models import F, Q
from rest_framework.exceptions import PermissionDenied

from aplicaciones.usuarios.tenancy import normalizar_nombre, resolver_alcance
from .especificacion import _valor
from .fuentes_operativas import _REGISTRO, metadatos_filtro, _nombre
from .seguridad import tiene_permiso, validar_json
from aplicaciones.personal.models import Profesor
from aplicaciones.usuarios.models import Admin, Usuario


_SUFIJOS = {'eq': '', 'ne': '', 'in': '__in', 'contains': '__icontains', 'startswith': '__istartswith', 'endswith': '__iendswith', 'gt': '__gt', 'gte': '__gte', 'lt': '__lt', 'lte': '__lte', 'date_gte': '__gte', 'date_lte': '__lte', 'before': '__lt', 'after': '__gt', 'between': '__range', 'isnull': '__isnull', 'notnull': '__isnull'}
_COMUN = {'eq', 'isnull', 'notnull'}
_OPERADORES_QBE = {
    'texto': _COMUN | {'contains', 'startswith', 'endswith', 'in'},
    'entero': _COMUN | {'ne', 'gt', 'gte', 'lt', 'lte', 'between', 'in'},
    'decimal': _COMUN | {'ne', 'gt', 'gte', 'lt', 'lte', 'between', 'in'},
    'fecha': _COMUN | {'before', 'after', 'between', 'date_gte', 'date_lte'},
    'booleano': _COMUN,
}


def _tipos(fuente):
    return {campo: tipo for campo, (_, tipo) in fuente['filtros_internos'].items()}


def _operadores(campo, tipo):
    if campo in ('genero', 'puesto'):
        return _COMUN | {'ne', 'in'}
    if campo in ('unidad', 'curso', 'periodo', 'materia'):
        return _COMUN | {'ne', 'in'}
    return _OPERADORES_QBE[tipo]


_PERSONAL = {
    'DOCENTES': {
        'nombre': 'Personal docente', 'modelo': Profesor, 'unidad_ruta': 'unidad',
        'permiso_fuente': 'profesor', 'condiciones': {},
        'campos': {'profesor_id': F('pk'), 'nombre_completo': _nombre(''), 'ci': F('usuario__ci'), 'genero': F('usuario__sexo'), 'unidad_educativa': F('unidad__nombre'), 'estado': F('estado')},
        'filtros_internos': {'unidad': ('unidad_id', 'entero'), 'genero': ('usuario__sexo', 'texto'), 'estado': ('estado', 'booleano')},
        'orden_interno': {'nombre_completo': 'usuario__apellido', 'unidad_educativa': 'unidad__nombre', 'genero': 'usuario__sexo'},
        'defecto': ['nombre_completo', 'unidad_educativa', 'estado'],
    },
    'PERSONAL_ADMINISTRATIVO': {
        'nombre': 'Personal administrativo', 'modelo': Admin, 'unidad_ruta': 'unidad',
        'permiso_fuente': 'usuario', 'colegio_directo': True,
        'condiciones': {'usuario__rol__nombre__iexact': 'Admin'},
        'campos': {'administrativo_id': F('pk'), 'nombre_completo': _nombre(''), 'ci': F('usuario__ci'), 'genero': F('usuario__sexo'), 'puesto': F('puesto__nombre'), 'colegio': F('colegio__nombre'), 'unidad_educativa': F('unidad__nombre'), 'estado': F('estado')},
        'filtros_internos': {'unidad': ('unidad_id', 'entero'), 'genero': ('usuario__sexo', 'texto'), 'estado': ('estado', 'booleano'), 'puesto': ('puesto_id', 'entero')},
        'orden_interno': {'nombre_completo': 'usuario__apellido', 'puesto': 'puesto__nombre', 'unidad_educativa': 'unidad__nombre', 'genero': 'usuario__sexo'},
        'defecto': ['nombre_completo', 'puesto', 'unidad_educativa', 'estado'],
    },
}


def puestos_autorizados(usuario):
    alcance = resolver_alcance(usuario)
    if alcance['tipo'] not in ('COLEGIO', 'UNIDAD') or not tiene_permiso(usuario, 'usuario', 'listar'):
        return []
    consulta = Admin.objects.filter(colegio_id=alcance['colegio_id'], usuario__rol__nombre__iexact='Admin').filter(
        Q(unidad__isnull=True) | Q(unidad__colegio_id=alcance['colegio_id'])
    )
    if alcance['tipo'] == 'UNIDAD':
        consulta = consulta.filter(unidad_id=alcance['unidad_id'])
    return list(consulta.filter(puesto__isnull=False).order_by('puesto__nombre', 'puesto_id').values_list('puesto_id', 'puesto__nombre').distinct())


def validar_puestos_alcance(usuario, codigo, spec):
    if codigo != 'PERSONAL_ADMINISTRATIVO':
        return
    def ids(nodo):
        if nodo.get('campo') == 'puesto' and nodo.get('valor') is not None:
            valor = nodo['valor']
            return valor if isinstance(valor, list) else [valor]
        return [valor for hijo in nodo.get('condiciones', []) for valor in ids(hijo)]
    solicitados = ids(spec['condiciones'])
    if solicitados and not set(solicitados).issubset({pk for pk, _ in puestos_autorizados(usuario)}):
        raise ValidationError('El puesto seleccionado no está disponible para su ámbito.')


def fuente_qbe(codigo):
    if codigo in _PERSONAL:
        return _PERSONAL[codigo]
    fuente = _REGISTRO.get(codigo)
    if fuente is not None and codigo == 'ESTUDIANTES_INSCRITOS':
        return {**fuente, 'campos': {**fuente['campos'], 'ci': F('usuario__ci'), 'rude': F('rude'), 'genero': F('usuario__sexo')}, 'filtros_internos': {**fuente['filtros_internos'], 'genero': ('usuario__sexo', 'texto')}, 'defecto': ['nombre', 'curso', 'unidad', 'activo']}
    return fuente


def autorizar_columnas_estudiante(usuario, codigo, columnas):
    fuente = fuente_qbe(codigo)
    if fuente and fuente.get('permiso_fuente') and not tiene_permiso(usuario, fuente['permiso_fuente'], 'listar'):
        raise PermissionDenied('No tiene permiso para consultar esta fuente.')
    if codigo == 'ESTUDIANTES_INSCRITOS' and {'ci', 'rude'}.intersection(columnas) and not tiene_permiso(usuario, 'estudiante', 'listar'):
        raise PermissionDenied('No tiene permiso para consultar datos de estudiantes.')


def catalogo_qbe(usuario=None):
    resultado = []
    for codigo in (*_REGISTRO, *_PERSONAL):
        fuente = fuente_qbe(codigo)
        if usuario is not None and fuente.get('permiso_fuente') and not tiene_permiso(usuario, fuente['permiso_fuente'], 'listar'):
            continue
        tipos = _tipos(fuente)
        columnas = []
        for campo in fuente['campos']:
            if usuario is not None and codigo == 'ESTUDIANTES_INSCRITOS' and campo in ('ci', 'rude') and not tiene_permiso(usuario, 'estudiante', 'listar'):
                continue
            tipo = tipos.get(campo, {
                'estudiante_id': 'entero', 'activo': 'booleano', 'promedio': 'decimal',
                'valor_detectado': 'decimal', 'umbral_aplicado': 'decimal', 'total': 'entero',
                'presentes': 'entero', 'ausentes': 'entero', 'atrasos': 'entero', 'licencias': 'entero',
                'fecha': 'fecha', 'detectado_at': 'fecha',
            }.get(campo, 'texto'))
            etiquetas = {'ci': 'Documento de identidad (CI)', 'rude': 'Código RUDE', 'nombre': 'Nombre completo', 'unidad': 'Unidad educativa', 'activo': 'Estado'}
            grupo = 'Identificación' if campo in ('estudiante_id', 'profesor_id', 'administrativo_id', 'nombre', 'nombre_completo', 'ci', 'rude', 'genero') else 'Información institucional' if campo in ('curso', 'unidad', 'unidad_educativa', 'puesto', 'colegio') else 'Estado' if campo in ('activo', 'estado') else 'Otras columnas'
            columnas.append({'campo': campo, 'etiqueta': 'Género' if campo == 'genero' else etiquetas.get(campo, campo.replace('_', ' ').capitalize()), 'tipo': tipo, 'seleccionable': True, 'sensible': campo in ('ci', 'rude'), 'filtrable': campo in tipos, 'ordenable': campo in fuente['orden_interno'], 'seleccionada_por_defecto': campo in fuente['defecto'], 'grupo': grupo})
        filtros = [{**metadatos_filtro(campo, tipo), 'operadores': sorted(_operadores(campo, tipo))} for campo, tipo in tipos.items()]
        for filtro in filtros:
            if filtro['campo'] == 'genero':
                filtro.update(etiqueta='Género', control='enumeracion', opciones=[{'valor': valor, 'etiqueta': etiqueta} for valor, etiqueta in Usuario._meta.get_field('sexo').choices])
            if filtro['campo'] == 'puesto':
                filtro.update(etiqueta='Puesto', control='enumeracion', opciones=[{'valor': str(pk), 'etiqueta': nombre} for pk, nombre in puestos_autorizados(usuario)] if usuario is not None else [])
        resultado.append({
            'codigo': codigo, 'etiqueta': fuente['nombre'], 'version': 1,
            'columnas': columnas,
            'filtros': filtros, 'predeterminadas': fuente['defecto'],
            'ordenables': sorted(fuente['orden_interno']), 'alcance': 'COLEGIO_O_UNIDAD',
        })
    return resultado


def _condicion(valor, tipos, profundidad=1, ids=None):
    ids = ids if ids is not None else set()
    if not isinstance(valor, dict):
        raise ValidationError('Condición inválida.')
    identificador = valor.get('id')
    if identificador is not None:
        if not isinstance(identificador, str) or not identificador or len(identificador) > 80 or identificador in ids:
            raise ValidationError('Identificador de condición inválido o duplicado.')
        ids.add(identificador)
    claves = set(valor) - {'id'}
    if claves in ({'campo', 'operador', 'valor'}, {'campo', 'operador'}):
        campo, operador = valor['campo'], valor['operador']
        if campo == 'puesto' and campo not in tipos:
            raise ValidationError('El campo Puesto solo está disponible para Personal administrativo.')
        if not isinstance(campo, str) or campo not in tipos or not isinstance(operador, str) or operador not in _operadores(campo, tipos[campo]):
            raise ValidationError('Campo u operador no permitido.')
        bruto = valor.get('valor')
        if campo == 'puesto' and operador not in ('isnull', 'notnull'):
            valores_puesto = bruto if isinstance(bruto, list) else [bruto]
            if any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in valores_puesto):
                raise ValidationError('Seleccione un puesto válido.')
        if operador in ('isnull', 'notnull'):
            if bruto is not None:
                raise ValidationError('El operador no admite valor.')
            normalizado = None
        elif operador in ('in', 'between'):
            if not isinstance(bruto, list) or not (len(bruto) == 2 if operador == 'between' else 1 <= len(bruto) <= 100):
                raise ValidationError('La lista debe tener entre uno y cien valores.')
            normalizado = [_valor(item, tipos[campo]) for item in bruto]
        else:
            normalizado = _valor(bruto, tipos[campo])
        if campo == 'genero' and normalizado is not None:
            permitidos = {valor for valor, _ in Usuario._meta.get_field('sexo').choices}
            valores = normalizado if isinstance(normalizado, list) else [normalizado]
            if any(valor not in permitidos for valor in valores):
                raise ValidationError('Seleccione una opción de género válida.')
        resultado = {'campo': campo, 'operador': operador, 'valor': normalizado}
        if identificador is not None:
            resultado['id'] = identificador
        return resultado, 1
    if claves != {'logica', 'condiciones'} or valor['logica'] not in ('AND', 'OR') or not isinstance(valor['condiciones'], list):
        raise ValidationError('Grupo lógico inválido.')
    if not valor['condiciones'] and profundidad != 1:
        raise ValidationError('Grupo lógico inválido.')
    if profundidad > 2 or len(valor['condiciones']) > 10:
        raise ValidationError('Profundidad o cantidad de condiciones no permitida.')
    hijos, total = [], 0
    for hijo in valor['condiciones']:
        try:
            normalizado, cantidad = _condicion(hijo, tipos, profundidad + 1, ids)
        except ValidationError as exc:
            if isinstance(hijo, dict) and isinstance(hijo.get('id'), str):
                detalle = getattr(exc, 'message_dict', None)
                if detalle:
                    raise
                raise ValidationError({hijo['id']: exc.messages}) from exc
            raise
        hijos.append(normalizado); total += cantidad
    grupo = {'logica': valor['logica'], 'condiciones': hijos}
    if identificador is not None:
        grupo['id'] = identificador
    return grupo, total


def validar_qbe(especificacion, fuente):
    if not isinstance(especificacion, dict) or set(especificacion) not in ({'columnas', 'condiciones', 'orden'}, {'columnas', 'condiciones', 'orden', 'limite'}):
        raise ValidationError('QBE requiere únicamente columnas, condiciones y orden.')
    validar_json(especificacion)
    columnas, orden = especificacion['columnas'], especificacion['orden']
    if not isinstance(columnas, list) or not columnas:
        raise ValidationError({'columnas': 'Seleccione al menos una columna.'})
    if len(columnas) > 15 or any(not isinstance(campo, str) or campo not in fuente['campos'] for campo in columnas) or len(set(columnas)) != len(columnas):
        raise ValidationError({'columnas': 'La definición utiliza columnas que no están disponibles para esta fuente.'})
    condiciones, cantidad = _condicion(especificacion['condiciones'], _tipos(fuente))
    if cantidad > 10:
        raise ValidationError('Se permiten hasta diez condiciones.')
    if not isinstance(orden, list) or len(orden) > 3:
        raise ValidationError({'orden': 'Se permiten hasta tres ordenamientos.'})
    vistos = set()
    for item in orden:
        if not isinstance(item, dict) or set(item) != {'campo', 'direccion'} or not isinstance(item['campo'], str) or item['campo'] not in fuente['orden_interno'] or item['campo'] in vistos or item['direccion'] not in ('asc', 'desc'):
            raise ValidationError({'orden': 'Orden QBE no permitido.'})
        vistos.add(item['campo'])
    resultado = {'columnas': list(columnas), 'condiciones': condiciones, 'orden': list(orden)}
    if 'limite' in especificacion:
        limite = especificacion['limite']
        if isinstance(limite, bool) or not isinstance(limite, int) or not 1 <= limite <= 5000:
            raise ValidationError({'limite': 'El límite debe estar entre 1 y 5000.'})
        resultado['limite'] = limite
    return resultado


def _q(condicion, fuente):
    if 'campo' in condicion:
        ruta = fuente['filtros_internos'][condicion['campo']][0]
        operador = condicion['operador']
        valor = operador == 'isnull' if operador in ('isnull', 'notnull') else condicion['valor']
        consulta = Q(**{ruta + _SUFIJOS[operador]: valor})
        return ~consulta if operador == 'ne' else consulta
    combinada = Q()
    for hijo in condicion['condiciones']:
        combinada = (combinada & _q(hijo, fuente)) if condicion['logica'] == 'AND' else (combinada | _q(hijo, fuente))
    return combinada


def ejecutar_qbe(usuario, codigo, especificacion, limite=100, unidad_id=None):
    alcance = resolver_alcance(usuario)
    puesto = normalizar_nombre(getattr(getattr(getattr(usuario, 'admin', None), 'puesto', None), 'nombre', ''))
    if puesto not in ('director', 'secretaria') or alcance['tipo'] not in ('COLEGIO', 'UNIDAD') or not tiene_permiso(usuario, 'reporte-qbe', 'ejecutar'):
        raise PermissionDenied('Permiso QBE no autorizado.')
    if fuente_qbe(codigo) is None or not isinstance(limite, int) or not 1 <= limite <= 5000:
        raise ValueError('Fuente o límite inválido.')
    fuente = fuente_qbe(codigo)
    spec = validar_qbe(especificacion, fuente)
    autorizar_columnas_estudiante(usuario, codigo, spec['columnas'])
    validar_puestos_alcance(usuario, codigo, spec)
    limite = min(limite, spec.get('limite', limite))
    ruta = fuente['unidad_ruta']
    filtros = {'colegio_id' if fuente.get('colegio_directo') else ruta + '__colegio_id': alcance['colegio_id']}
    if alcance['tipo'] == 'UNIDAD':
        filtros[ruta + '_id'] = alcance['unidad_id']
    if unidad_id is not None:
        if unidad_id != alcance['unidad_id'] and alcance['tipo'] == 'UNIDAD':
            raise PermissionDenied('Unidad fuera del alcance.')
        filtros[ruta + '_id'] = unidad_id
    queryset = fuente['modelo'].objects.filter(**filtros).filter(**fuente['condiciones']).filter(_q(spec['condiciones'], fuente))
    if fuente.get('colegio_directo'):
        queryset = queryset.filter(Q(unidad__isnull=True) | Q(unidad__colegio_id=alcance['colegio_id']))
    orden = [('-' if item['direccion'] == 'desc' else '') + fuente['orden_interno'][item['campo']] for item in spec['orden']]
    aliases = {'reporte_' + campo: fuente['campos'][campo] for campo in spec['columnas']}
    if fuente.get('agregada'):
        grupo = ['historial_inscripcion__estudiante_id', 'historial_inscripcion__estudiante__usuario__nombre', 'historial_inscripcion__estudiante__usuario__apellido', 'historial_inscripcion__curso_nuevo__nombre', 'historial_inscripcion__unidad__nombre']
        agregados = dict(aliases)
        if any(item['campo'] == 'total' for item in spec['orden']):
            agregados['total'] = fuente['campos']['total']
        filas = list(queryset.values(*grupo).annotate(**agregados).order_by(*(orden + ['historial_inscripcion__estudiante_id'])).values(*aliases)[:limite + 1])
    else:
        filas = list(queryset.order_by(*(orden + ['pk'])).annotate(**aliases).values(*aliases)[:limite + 1])
    return spec, [[fila['reporte_' + campo] for campo in spec['columnas']] for fila in filas[:limite]], len(filas) > limite

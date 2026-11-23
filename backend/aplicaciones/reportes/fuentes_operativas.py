"""Adaptadores cerrados de lectura; nunca aceptan rutas ORM del cliente."""
from django.db.models import Count, F, Q, Value
from django.db.models.functions import Concat
from rest_framework.exceptions import PermissionDenied

from aplicaciones.academico.models import ResultadoTrimestral
from aplicaciones.estudiantes.models import AsistenciaEstudiante, Estudiante, IncidenteDisciplinario
from aplicaciones.usuarios.tenancy import normalizar_nombre, resolver_alcance
from .especificacion import OPERADORES, validar_especificacion
from .seguridad import tiene_permiso


def _nombre(ruta):
    prefijo = ruta + '__' if ruta else ''
    return Concat(F(prefijo + 'usuario__nombre'), Value(' '), F(prefijo + 'usuario__apellido'))


# Las rutas y expresiones solo existen en el servidor y no se publican.
_REGISTRO = {
    'ESTUDIANTES_INSCRITOS': {
        'nombre': 'Estudiantes inscritos actualmente',
        'descripcion': 'Estado actual de estudiantes e inscripción vigente',
        'modelo': Estudiante, 'unidad_ruta': 'unidad',
        'campos': {'estudiante_id': F('pk'), 'nombre': _nombre(''),
                   'curso': F('curso__nombre'), 'unidad': F('unidad__nombre'), 'activo': F('estado')},
        'filtros_internos': {'unidad': ('unidad_id', 'entero'), 'curso': ('curso_id', 'entero'), 'activo': ('estado', 'booleano')},
        'orden_interno': {'estudiante_id': 'pk', 'curso': 'curso__nombre'},
        'condiciones': {'estado': True, 'curso__isnull': False, 'unidad__isnull': False, 'curso__paralelo__grado__unidad_educativa_id': F('unidad_id')},
        'defecto': ['nombre', 'curso', 'unidad'],
    },
    'RENDIMIENTO_ACADEMICO': {
        'nombre': 'Resultados trimestrales',
        'descripcion': 'Resultados existentes asociados a la inscripción y periodo.',
        'modelo': ResultadoTrimestral, 'unidad_ruta': 'historial_inscripcion__unidad',
        'campos': {'estudiante_id': F('historial_inscripcion__estudiante_id'), 'nombre': _nombre('historial_inscripcion__estudiante'),
                   'curso': F('historial_inscripcion__curso_nuevo__nombre'), 'unidad': F('historial_inscripcion__unidad__nombre'),
                   'materia': F('materia__nombre'), 'periodo': F('periodo__nombre'), 'promedio': F('resultado'), 'estado': F('estado')},
        'filtros_internos': {'unidad': ('historial_inscripcion__unidad_id', 'entero'), 'curso': ('historial_inscripcion__curso_nuevo_id', 'entero'),
                             'periodo': ('periodo_id', 'entero'), 'materia': ('materia_id', 'entero'), 'promedio': ('resultado', 'decimal')},
        'orden_interno': {'promedio': 'resultado', 'periodo': 'periodo__fecha_inicio'},
        'condiciones': {'periodo__calendario__unidad_educativa_id': F('historial_inscripcion__unidad_id'),
                        'historial_inscripcion__curso_nuevo__paralelo__grado__unidad_educativa_id': F('historial_inscripcion__unidad_id')},
        'defecto': ['nombre', 'curso', 'materia', 'periodo', 'promedio'],
    },
    'ASISTENCIA_RESUMEN': {
        'nombre': 'Resumen de asistencia',
        'descripcion': 'Conteo de asistencias por estudiante dentro del alcance y los filtros seleccionados.',
        'modelo': AsistenciaEstudiante, 'unidad_ruta': 'historial_inscripcion__unidad', 'agregada': True,
        'campos': {'estudiante_id': F('historial_inscripcion__estudiante_id'),
                   'nombre': _nombre('historial_inscripcion__estudiante'),
                   'curso': F('historial_inscripcion__curso_nuevo__nombre'),
                   'unidad': F('historial_inscripcion__unidad__nombre'),
                   'total': Count('pk'),
                   'presentes': Count('pk', filter=Q(estado_asistencia='PRESENTE')),
                   'ausentes': Count('pk', filter=Q(estado_asistencia='AUSENTE')),
                   'atrasos': Count('pk', filter=Q(estado_asistencia='ATRASO')),
                   'licencias': Count('pk', filter=Q(estado_asistencia='LICENCIA'))},
        'filtros_internos': {'unidad': ('historial_inscripcion__unidad_id', 'entero'),
                             'curso': ('historial_inscripcion__curso_nuevo_id', 'entero'),
                             'fecha': ('sesion_clase__fecha', 'fecha'),
                             'estado_asistencia': ('estado_asistencia', 'texto')},
        'orden_interno': {'nombre': 'historial_inscripcion__estudiante__usuario__apellido',
                          'curso': 'historial_inscripcion__curso_nuevo__nombre', 'total': 'total'},
        'condiciones': {'historial_inscripcion__curso_nuevo__paralelo__grado__unidad_educativa_id': F('historial_inscripcion__unidad_id')},
        'defecto': ['nombre', 'curso', 'total', 'presentes', 'ausentes', 'atrasos', 'licencias'],
    },
    'INCIDENTES_DISCIPLINARIOS': {
        'nombre': 'Incidentes disciplinarios',
        'descripcion': 'Incidentes vinculados a la inscripción histórica.',
        'modelo': IncidenteDisciplinario, 'unidad_ruta': 'historial_inscripcion__unidad',
        'campos': {'estudiante_id': F('historial_inscripcion__estudiante_id'), 'nombre': _nombre('historial_inscripcion__estudiante'),
                   'curso': F('historial_inscripcion__curso_nuevo__nombre'), 'unidad': F('historial_inscripcion__unidad__nombre'),
                   'tipo': F('tipo'), 'severidad': F('severidad'), 'estado': F('estado'), 'fecha': F('fecha')},
        'filtros_internos': {'unidad': ('historial_inscripcion__unidad_id', 'entero'), 'curso': ('historial_inscripcion__curso_nuevo_id', 'entero'),
                             'estado': ('estado', 'texto'), 'severidad': ('severidad', 'texto')},
        'orden_interno': {'fecha': 'fecha', 'severidad': 'severidad'},
        'condiciones': {'historial_inscripcion__curso_nuevo__paralelo__grado__unidad_educativa_id': F('historial_inscripcion__unidad_id')},
        'defecto': ['nombre', 'curso', 'tipo', 'severidad', 'estado', 'fecha'],
    },
}


def _esquema(fuente):
    return {'columnas': set(fuente['campos']), 'filtros': {k: v[1] for k, v in fuente['filtros_internos'].items()},
            'ordenables': set(fuente['orden_interno'])}


def metadatos_filtro(campo, tipo):
    controles = {'unidad': 'unidad', 'curso': 'curso', 'periodo': 'periodo', 'materia': 'materia'}
    etiquetas = {'unidad': 'Unidad educativa', 'curso': 'Curso', 'periodo': 'Periodo', 'materia': 'Materia'}
    resultado = {'campo': campo, 'etiqueta': etiquetas.get(campo, campo.replace('_', ' ').capitalize()),
                 'tipo': tipo, 'control': controles.get(campo, tipo), 'requerido': False,
                 'operadores': sorted(OPERADORES[tipo])}
    if campo == 'curso':
        resultado['depende_de'] = 'unidad'
    return resultado


def catalogo_operativo():
    return [{'codigo': codigo, 'nombre': f['nombre'], 'descripcion': f['descripcion'], 'version': 1,
             'columnas': [{'campo': c, 'etiqueta': c.replace('_', ' ').capitalize(),
                           'tipo': {'estudiante_id': 'entero', 'activo': 'booleano',
                                    'promedio': 'decimal', 'valor_detectado': 'decimal', 'umbral_aplicado': 'decimal',
                                    'total': 'entero', 'presentes': 'entero', 'ausentes': 'entero', 'atrasos': 'entero',
                                    'licencias': 'entero', 'fecha': 'fecha', 'detectado_at': 'fecha'}.get(c, 'texto')}
                          for c in f['campos']],
             'predeterminadas': f['defecto'][:],
             'filtros': [metadatos_filtro(k, v[1])
                         for k, v in f['filtros_internos'].items()],
             'ordenables': list(f['orden_interno']), 'limite': 100}
            for codigo, f in _REGISTRO.items()]


def ejecutar_fuente(usuario, codigo, especificacion, limite=100, unidad_id=None):
    """Filtra el tenant antes de filtros; devuelve hasta limite+1 para detectar exceso."""
    alcance = resolver_alcance(usuario)
    if not hasattr(usuario, 'admin') or normalizar_nombre(getattr(usuario.admin.puesto, 'nombre', '')) not in {'director', 'secretaria'}:
        raise PermissionDenied('Perfil no autorizado.')
    if alcance['tipo'] not in ('COLEGIO', 'UNIDAD') or not tiene_permiso(usuario, 'reporte-ejecucion', 'ejecutar'):
        raise PermissionDenied('Permiso o contexto no autorizado.')
    if codigo not in _REGISTRO or not isinstance(limite, int) or not 1 <= limite <= 5000:
        raise ValueError('Fuente o límite inválido.')
    fuente = _REGISTRO[codigo]
    spec = validar_especificacion(especificacion, _esquema(fuente))
    ruta = fuente['unidad_ruta']
    filtros_tenant = {ruta + '__colegio_id': alcance['colegio_id']}
    if alcance['tipo'] == 'UNIDAD':
        filtros_tenant[ruta + '_id'] = alcance['unidad_id']
    if unidad_id is not None:
        from aplicaciones.institucion.models import UnidadEducativa
        if (alcance['tipo'] == 'UNIDAD' and unidad_id != alcance['unidad_id']) or not UnidadEducativa.objects.filter(pk=unidad_id, colegio_id=alcance['colegio_id']).exists():
            raise PermissionDenied('Unidad fuera del alcance.')
        filtros_tenant[ruta + '_id'] = unidad_id
    queryset = fuente['modelo'].objects.filter(**filtros_tenant).filter(**fuente['condiciones'])
    sufijos = {'eq': '', 'in': '__in', 'contains': '__icontains', 'gte': '__gte', 'lte': '__lte', 'date_gte': '__gte', 'date_lte': '__lte'}
    for filtro in spec['filtros']:
        ruta_filtro = fuente['filtros_internos'][filtro['campo']][0]
        queryset = queryset.filter(**{ruta_filtro + sufijos[filtro['operador']]: filtro['valor']})
    orden = [('-' if x['direccion'] == 'desc' else '') + fuente['orden_interno'][x['campo']] for x in spec['orden']]
    expresiones = {k: fuente['campos'][k] for k in spec['columnas']}
    # aliases no colisionan con nombres de campos de los modelos.
    aliases = {'reporte_' + k: v for k, v in expresiones.items()}
    if fuente.get('agregada'):
        agrupacion = [
            'historial_inscripcion__estudiante_id',
            'historial_inscripcion__estudiante__usuario__nombre',
            'historial_inscripcion__estudiante__usuario__apellido',
            'historial_inscripcion__curso_nuevo__nombre',
            'historial_inscripcion__unidad__nombre',
        ]
        queryset = queryset.values(*agrupacion).annotate(**aliases)
        filas = list(queryset.order_by(*(orden + ['historial_inscripcion__estudiante_id'])).values(*aliases)[:limite + 1])
    else:
        filas = list(queryset.order_by(*(orden + ['pk'])).annotate(**aliases).values(*aliases)[:limite + 1])
    return spec, [[fila['reporte_' + c] for c in spec['columnas']] for fila in filas[:limite]], len(filas) > limite

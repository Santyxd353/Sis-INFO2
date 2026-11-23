"""Exportador lógico filtrado por tenant y con estructura técnica comprensible."""
import hashlib
import json
import re
import zipfile
from pathlib import Path

from django.apps import apps
from django.db.models import Q

SENSITIVE = {'access', 'refresh', 'token', 'secret', 'clave', 'password', 'session', 'codigo_temporal', 'api_key', 'blacklist', 'ruta_interna'}


def _value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _row(obj):
    data = {}
    for field in obj._meta.concrete_fields:
        name = field.name
        if any(part in name.lower() for part in SENSITIVE):
            continue
        data[name + '_id' if field.is_relation else name] = _value(getattr(obj, field.attname if field.is_relation else name))
    return data


def _model_file(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _querysets(colegio_id):
    Unidad = _model_file('institucion', 'UnidadEducativa')
    Colegio = _model_file('institucion', 'Colegio')
    unidades = Unidad.objects.filter(colegio_id=colegio_id) if Unidad else None
    specs = []
    if Colegio:
        specs.append(('institucion', Colegio, Colegio.objects.filter(pk=colegio_id)))
    if Unidad:
        specs.append(('institucion', Unidad, unidades))
    Modulo = _model_file('institucion', 'Modulo')
    modulos = Modulo.objects.filter(Q(colegio_fk_id=colegio_id) | Q(unidad_educativa__colegio_id=colegio_id)).distinct() if Modulo else None
    if Modulo:
        specs.append(('institucion', Modulo, modulos))
    Aula = _model_file('institucion', 'Aula')
    aulas = Aula.objects.filter(modulo_id__in=modulos.values('pk')) if Aula and modulos is not None else None
    if Aula:
        specs.append(('institucion', Aula, aulas))
    Grado = _model_file('academico', 'Grado')
    grados = Grado.objects.filter(unidad_educativa_id__in=unidades.values('pk')) if Grado and unidades is not None else None
    if Grado:
        specs.append(('academico', Grado, grados))
    Paralelo = _model_file('academico', 'Paralelo')
    paralelos = Paralelo.objects.filter(grado_id__in=grados.values('pk')) if Paralelo and grados is not None else None
    if Paralelo:
        specs.append(('academico', Paralelo, paralelos))
    Curso = _model_file('academico', 'Curso')
    cursos = Curso.objects.filter(paralelo_id__in=paralelos.values('pk')) if Curso and paralelos is not None else None
    if Curso:
        specs.append(('academico', Curso, cursos))
    Materia = _model_file('academico', 'Materia')
    if Materia and unidades is not None:
        specs.append(('academico', Materia, Materia.objects.filter(unidad_educativa_id__in=unidades.values('pk'))))
    MateriaCurso = _model_file('academico', 'MateriaCurso')
    if MateriaCurso and cursos is not None:
        specs.append(('academico', MateriaCurso, MateriaCurso.objects.filter(curso_id__in=cursos.values('pk'))))
    for label, model_name, lookup in [
        ('personal', 'Profesor', {'unidad_id__in': unidades.values('pk')} if unidades is not None else {}),
        ('estudiantes', 'Estudiante', {'unidad_id__in': unidades.values('pk')} if unidades is not None else {}),
        ('usuarios', 'Admin', {'colegio_id': colegio_id}),
        ('calendario', 'CalendarioAcademico', {'unidad_educativa_id__in': unidades.values('pk')} if unidades is not None else {}),
    ]:
        model = _model_file(label, model_name)
        if model:
            specs.append((label, model, model.objects.filter(**lookup)))
    Usuario = _model_file('usuarios', 'Usuario')
    if Usuario:
        specs.append(('usuarios', Usuario, Usuario.objects.filter(Q(admin__colegio_id=colegio_id) | Q(admin__unidad__colegio_id=colegio_id) | Q(profesor__unidad__colegio_id=colegio_id) | Q(estudiante__unidad__colegio_id=colegio_id) | Q(tutor__estudiantes__estudiante__unidad__colegio_id=colegio_id)).distinct()))
    Calendario = _model_file('calendario', 'CalendarioAcademico')
    if Calendario and unidades is not None:
        calendarios = Calendario.objects.filter(unidad_educativa_id__in=unidades.values('pk'))
        for model_name in ('Periodo', 'Feriado'):
            model = _model_file('calendario', model_name)
            if model:
                specs.append(('calendario', model, model.objects.filter(calendario_id__in=calendarios.values('pk'))))
    return specs


def _safe_component_name(value):
    return re.sub(r'[^a-zA-Z0-9_.-]+', '_', value).strip('_') or 'componente'


def generar_respaldo_colegio(colegio_id, destino, respaldo_id):
    """Crea un .edubackup ZIP con LEEME, manifest, resumen y datos separados."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    specs = _querysets(colegio_id)
    componentes, checksums = [], {}
    colegio_model = _model_file('institucion', 'Colegio')
    colegio = colegio_model.objects.filter(pk=colegio_id).first() if colegio_model else None
    colegio_nombre = getattr(colegio, 'nombre', f'Colegio {colegio_id}')
    with zipfile.ZipFile(destino, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archivo:
        for app_label, model, queryset in specs:
            nombre = f'{app_label}.{model._meta.model_name}'
            interno = f'datos/{_safe_component_name(nombre)}.jsonl'
            filas = [_row(obj) for obj in queryset.order_by('pk')]
            contenido = ''.join(json.dumps(fila, ensure_ascii=False, sort_keys=True, default=str) + '\n' for fila in filas).encode('utf-8')
            archivo.writestr(interno, contenido)
            digest = hashlib.sha256(contenido).hexdigest()
            checksums[interno] = digest
            componentes.append({'modelo': nombre, 'archivo': interno, 'registros': len(filas), 'sha256': digest})
    omitidos = [
        {'modelo': 'usuarios.Token', 'clasificacion': 'SENSIBLE_EXCLUIDO', 'razon': 'tokens de autenticación excluidos'},
        {'modelo': 'usuarios.OutstandingToken', 'clasificacion': 'SENSIBLE_EXCLUIDO', 'razon': 'tokens JWT excluidos'},
        {'modelo': 'usuarios.BlacklistedToken', 'clasificacion': 'SENSIBLE_EXCLUIDO', 'razon': 'lista negra excluida'},
        {'modelo': 'django.contrib.sessions.Session', 'clasificacion': 'SENSIBLE_EXCLUIDO', 'razon': 'sesiones excluidas'},
        {'modelo': 'suscripciones.PlanSuscripcion', 'clasificacion': 'GLOBAL_REFERENCIADO', 'razon': 'catálogo global no pertenece a un tenant'},
    ]
    manifest = {'version_formato': 2, 'alcance': 'COLEGIO', 'colegio_id': colegio_id, 'colegio_nombre': colegio_nombre, 'respaldo_id': str(respaldo_id), 'componentes': componentes, 'archivos': [], 'checksums': checksums, 'omitidos': omitidos, 'politica_sensible': 'No se exportan contraseñas, tokens, secretos ni sesiones. La copia lógica del colegio no contiene hashes.', 'advertencia': 'Copia lógica filtrada por colegio; restauración exclusiva por administrador técnico.'}
    resumen = {'alcance': 'COLEGIO', 'colegio_id': colegio_id, 'componentes': len(componentes), 'registros_totales': sum(c['registros'] for c in componentes), 'version_formato': 2}
    leeme = f'Colegio: {colegio_nombre}\nAlcance: COLEGIO\nVersión: 2\nComponentes: {len(componentes)}\nRegistros: {resumen["registros_totales"]}\nCopia técnica privada. Contiene información sensible; no editar.\nLa restauración debe ser realizada por el administrador técnico.\n'
    with zipfile.ZipFile(destino, 'a', compression=zipfile.ZIP_DEFLATED) as archivo:
        archivo.writestr('LEEME.txt', leeme)
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8')
        resumen_bytes = json.dumps(resumen, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8')
        archivo.writestr('manifest.json', manifest_bytes)
        archivo.writestr('resumen.json', resumen_bytes)
        checksums['LEEME.txt'] = hashlib.sha256(leeme.encode('utf-8')).hexdigest()
        checksums['manifest.json'] = hashlib.sha256(manifest_bytes).hexdigest()
        checksums['resumen.json'] = hashlib.sha256(resumen_bytes).hexdigest()
        archivo.writestr('checksums.json', json.dumps(checksums, ensure_ascii=False, indent=2, sort_keys=True))
    return manifest

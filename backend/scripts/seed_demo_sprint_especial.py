"""Seed de demostración del sprint especial: 4 registros de ejemplo por funcionalidad.

1. HU-SE03 bitácora de seguridad: 4 eventos de auditoría inmutables
   (login, creación de rol, actualización de permisos, exportación de respaldo).
2. Pagos QR Vendis: suscripción demo del colegio con 4 pagos por pasarela QR
   (pendiente, validado, rechazado y expirado).
3. Respaldos .edubackup: 4 respaldos de colegio completados (1 real generado con
   el servicio oficial y 3 copias de demostración con archivo descargable).
4. Boletines HU-19 + notificaciones push: 4 boletines PDF del estudiante demo
   (trimestres 1-3 y anual), 3 dispositivos push y 4 notificaciones internas.

Requisito: haber corrido antes scripts/seed_demo_se02.py (usuarios/colegio demo).
Uso:  python scripts/seed_demo_sprint_especial.py
Idempotente: cada sección se omite si sus 4 ejemplos ya existen.
"""
import hashlib
import os
import shutil
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.utils import timezone  # noqa: E402

from aplicaciones.academico.models import (  # noqa: E402
    ActividadEvaluacion, AsignacionDocente, Calificacion, Curso, DimensionEvaluacion,
    Grado, Materia, MateriaCurso, Paralelo,
)
from aplicaciones.academico.resultados import calcular_resultado_trimestral  # noqa: E402
from aplicaciones.calendario.models import CalendarioAcademico, Periodo  # noqa: E402
from aplicaciones.estudiantes import boletines  # noqa: E402
from aplicaciones.estudiantes.models import (  # noqa: E402
    DocumentoAcademicoEmitido, Estudiante, HistorialInscripcion, Tutor, TutorEstudiante,
)
from aplicaciones.estudiantes.views import DocumentoAcademicoEmitidoViewSet  # noqa: E402
from aplicaciones.institucion.models import Colegio, UnidadEducativa  # noqa: E402
from aplicaciones.personal.models import Profesor  # noqa: E402
from aplicaciones.respaldos import servicios as servicios_respaldo  # noqa: E402
from aplicaciones.respaldos.models import Respaldo  # noqa: E402
from aplicaciones.suscripciones.models import Plan, Pago, Suscripcion  # noqa: E402
from aplicaciones.usuarios.auditoria import registrar_evento  # noqa: E402
from aplicaciones.usuarios.models import (  # noqa: E402
    DispositivoNotificacion, EventoAuditoria, Notificacion, Usuario,
)


def sembrar_auditoria_hu_se03(admin, director, colegio, unidad):
    """HU-SE03: 4 eventos de la bitácora de seguridad (inmutables)."""
    print('HU-SE03 bitácora de seguridad')
    marcador = {'fuente': 'seed_demo_sprint_especial'}
    if EventoAuditoria.objects.filter(cambios_sanitizados__contains=marcador).count() >= 4:
        print('  = 4 eventos de auditoría ya existían')
        return
    registrar_evento(
        accion='LOGIN_EXITOSO', entidad='AUTENTICACION', usuario=admin,
        entidad_id=str(admin.pk), cambios={'fuente': 'seed_demo_sprint_especial', 'metodo': 'password'},
        correlacion=uuid.UUID('aaaaaaaa-0001-4000-8000-000000000001'),
    )
    registrar_evento(
        accion='CREAR', entidad='ROL', usuario=director, entidad_id='6',
        colegio=colegio, unidad=unidad,
        cambios={'fuente': 'seed_demo_sprint_especial', 'campos': ['nombre', 'colegio'], 'resultado': 'Coordinador Demo'},
        correlacion=uuid.UUID('aaaaaaaa-0002-4000-8000-000000000002'),
    )
    registrar_evento(
        accion='ACTUALIZAR', entidad='PERMISO_ROL', usuario=director, entidad_id='6',
        colegio=colegio, unidad=unidad,
        cambios={'fuente': 'seed_demo_sprint_especial', 'campos': ['permisos'], 'resultado': '2 permisos'},
        correlacion=uuid.UUID('aaaaaaaa-0003-4000-8000-000000000003'),
    )
    registrar_evento(
        accion='EXPORTAR', entidad='RESPALDO', usuario=admin,
        cambios={'fuente': 'seed_demo_sprint_especial', 'alcance': 'COLEGIO', 'resultado': 'exitoso'},
        correlacion=uuid.UUID('aaaaaaaa-0004-4000-8000-000000000004'),
    )
    print('  + 4 eventos: LOGIN_EXITOSO, CREAR/ROL, ACTUALIZAR/PERMISO_ROL, EXPORTAR/RESPALDO')


def sembrar_pagos_qr(admin, colegio):
    """Pasarela QR Vendis: 4 estados posibles de un pago por QR."""
    print('Pagos QR Vendis')
    plan, _ = Plan.objects.get_or_create(
        nombre='Plan Demo Institucional',
        defaults={
            'descripcion': 'Plan de demostración para el sprint especial (pagos QR).',
            'precio': Decimal('500.00'), 'moneda': 'BOB', 'periodicidad': 'MENSUAL',
            'modulos_habilitados': ['comunicaciones', 'notificaciones'],
        },
    )
    suscripcion, creada = Suscripcion.objects.get_or_create(
        colegio=colegio, plan=plan,
        defaults={
            'precio_periodico': Decimal('500.00'), 'moneda': 'BOB', 'periodicidad': 'MENSUAL',
            'modulos_habilitados': plan.modulos_habilitados,
            'fecha_inicio': date(2026, 10, 1), 'fecha_vencimiento': date(2026, 11, 1),
            'estado': Suscripcion.Estado.ACTIVA,
        },
    )
    if creada:
        print('  + suscripción demo ACTIVA creada')

    hoy = timezone.now()
    ejemplos = [
        {
            'qr_id': 'demo-qr-001',
            'resultado': Pago.Resultado.PENDIENTE,
            'observacion': 'Generación QR pendiente de confirmación por Vendis.',
            'qr_expira_at': hoy + timedelta(hours=1),
        },
        {
            'qr_id': 'demo-qr-002',
            'resultado': Pago.Resultado.VALIDADO,
            'observacion': 'Pago QR confirmado por Vendis (webhook).',
            'qr_expira_at': hoy - timedelta(hours=2),
            'validado': True,
        },
        {
            'qr_id': 'demo-qr-003',
            'resultado': Pago.Resultado.RECHAZADO,
            'observacion': 'Pasarela rechazó el pago: monto no coincidente.',
            'qr_expira_at': hoy - timedelta(hours=3),
        },
        {
            'qr_id': 'demo-qr-004',
            'resultado': Pago.Resultado.PENDIENTE,
            'observacion': 'QR expirado; requiere conciliación manual.',
            'qr_expira_at': hoy - timedelta(days=1),
        },
    ]
    creados = 0
    for indice, ejemplo in enumerate(ejemplos, start=1):
        _, creado = Pago.objects.get_or_create(
            qr_id=ejemplo['qr_id'],
            defaults={
                'suscripcion': suscripcion,
                'metodo': 'PASARELA',
                'referencia': f'VENDIS-DEMO-{indice:03d}',
                'monto': suscripcion.precio_periodico,
                'moneda': 'BOB',
                'fecha': date(2026, 10, 10 + indice),
                'resultado': ejemplo['resultado'],
                'observacion': ejemplo['observacion'],
                'qr_url': f'https://qr-dev.cobranza.emizor.com/api/v1/devices/simple-qr/{ejemplo["qr_id"]}',
                'qr_expira_at': ejemplo['qr_expira_at'],
                'validado_por': admin if ejemplo.get('validado') else None,
                'validado_at': (hoy - timedelta(hours=2)) if ejemplo.get('validado') else None,
            },
        )
        if creado:
            creados += 1
    print(f'  + {creados} pagos QR (pendiente, validado, rechazado, expirado)')


def sembrar_respaldos(admin, colegio):
    """Respaldos .edubackup: 4 registros completados con archivo descargable."""
    print('Respaldos .edubackup')
    existentes = Respaldo.objects.filter(
        alcance=Respaldo.ALCANCE_COLEGIO, colegio=colegio, archivo__startswith='respaldo_colegio_',
    )
    if existentes.count() >= 4:
        print('  = 4 respaldos ya existían')
        return

    if not existentes.exclude(archivo='').exists():
        servicios_respaldo.encolar('MANUAL', admin, alcance='COLEGIO', colegio=colegio)
        procesado = servicios_respaldo.ejecutar_pendiente()
        print(f'  + respaldo real del colegio ejecutado: {procesado}')
    base = existentes.exclude(archivo='').order_by('solicitado_at').first()
    if base is None or not base.archivo:
        raise RuntimeError('No se pudo generar el respaldo base del colegio.')
    ruta_base = Path(settings.RESPALDOS_ROOT) / base.archivo
    if not ruta_base.is_file():
        raise RuntimeError(f'Falta el archivo del respaldo base: {base.archivo}')

    contenido = ruta_base.read_bytes()
    digest = hashlib.sha256(contenido).hexdigest()
    marcas = [
        (date(2026, 10, 28), 'PROGRAMADO', 'Respaldo programado nocturno.'),
        (date(2026, 10, 29), 'MANUAL', 'Respaldo manual antes del cierre mensual.'),
        (date(2026, 10, 30), 'PROGRAMADO', 'Respaldo programado de verificación.'),
    ]
    creados = 0
    for dia, origen, detalle in marcas:
        nombre = f'respaldo_colegio_{colegio.pk}_{dia:%Y%m%d}_0230.edubackup'
        ruta = Path(settings.RESPALDOS_ROOT) / nombre
        if not ruta.is_file():
            shutil.copyfile(ruta_base, ruta)
        respaldo, creado = Respaldo.objects.get_or_create(
            archivo=nombre,
            defaults={
                'origen': origen,
                'estado': 'COMPLETADO',
                'alcance': Respaldo.ALCANCE_COLEGIO,
                'colegio': colegio,
                'solicitado_por': admin,
                'tamano': len(contenido),
                'sha256': digest,
                'version_formato': base.version_formato,
                'metadatos': {'demo': True, 'detalle': detalle},
            },
        )
        if creado:
            creados += 1
            Respaldo.objects.filter(pk=respaldo.pk).update(
                solicitado_at=timezone.make_aware(datetime(dia.year, dia.month, dia.day, 2, 30)),
            )
    print(f'  + {creados + 1} respaldos COMPLETADO con archivo (1 real + {creados} copias)')


def sembrar_boletines_y_notificaciones(unidad, director, profesor_usuario, estudiante_usuario, tutor_usuario):
    """HU-19: 4 boletines PDF (T1-T3 + anual), 3 dispositivos push y 4 notificaciones."""
    print('Boletines HU-19 + notificaciones push')
    profesor = Profesor.objects.get(usuario=profesor_usuario)
    estudiante = Estudiante.objects.get(usuario=estudiante_usuario)
    tutor = Tutor.objects.get(usuario=tutor_usuario)

    grado, _ = Grado.objects.get_or_create(unidad_educativa=unidad, nivel_educativo='PRI', numero=4)
    paralelo, _ = Paralelo.objects.get_or_create(grado=grado, letra='A')
    curso, _ = Curso.objects.get_or_create(paralelo=paralelo, defaults={'nombre': '4to A Demo'})
    materia, _ = Materia.objects.get_or_create(nombre='Matemática Demo', unidad_educativa=unidad)
    materia_curso, _ = MateriaCurso.objects.get_or_create(
        curso=curso, materia=materia, defaults={'profesor': profesor},
    )
    gestion, _ = CalendarioAcademico.objects.get_or_create(
        unidad_educativa=unidad, año=2026,
        defaults={'fecha_inicio': date(2026, 2, 1), 'fecha_fin': date(2026, 11, 30), 'activo': True},
    )
    if estudiante.curso_id != curso.pk:
        estudiante.curso = curso
        estudiante.save(update_fields=['curso'])
    historial = HistorialInscripcion.objects.filter(estudiante=estudiante, curso_nuevo=curso).first()
    if historial is None:
        historial = HistorialInscripcion.objects.create(
            estudiante=estudiante, curso_nuevo=curso, unidad=unidad, tipo_movimiento='NUEVA',
        )
    TutorEstudiante.objects.get_or_create(tutor=tutor, estudiante=estudiante, defaults={'es_principal': True})
    asignacion, _ = AsignacionDocente.objects.get_or_create(
        tipo='MATERIA', calendario_academico=gestion, curso=curso, materia_curso=materia_curso,
        profesor=profesor, defaults={'fecha_inicio': date(2026, 2, 10)},
    )
    dim_saber = DimensionEvaluacion.objects.get(
        configuracion__calendario_academico=gestion, configuracion__nivel='PRI', codigo='SABER',
    )

    emitidos = DocumentoAcademicoEmitido.objects.filter(tipo='BOLETIN', historial_inscripcion=historial)
    if emitidos.count() >= 4:
        print(f'  = {emitidos.count()} boletines ya existían')
    else:
        periodos = [
            ('Trimestre 1', date(2026, 2, 1), date(2026, 5, 31), Decimal('90')),
            ('Trimestre 2', date(2026, 6, 1), date(2026, 8, 15), Decimal('85')),
            ('Trimestre 3', date(2026, 8, 16), date(2026, 11, 30), Decimal('92')),
        ]
        for nombre, inicio, fin, valor in periodos:
            periodo, _ = Periodo.objects.get_or_create(
                calendario=gestion, tipo_division='TRI', nombre=nombre,
                defaults={'fecha_inicio': inicio, 'fecha_fin': fin, 'estado': 'CUR'},
            )
            actividad, _ = ActividadEvaluacion.objects.get_or_create(
                asignacion_docente=asignacion, periodo=periodo, dimension=dim_saber,
                nombre=f'Examen Demo {nombre}',
                defaults={'fecha': inicio + timedelta(days=40), 'puntaje_maximo': Decimal('100')},
            )
            Calificacion.objects.get_or_create(
                actividad=actividad, historial_inscripcion=historial,
                defaults={'valor': valor},
            )
            calcular_resultado_trimestral(historial, materia, periodo)
            if not emitidos.filter(periodo=periodo).exists():
                documento, _ = boletines.emitir_boletin(historial, gestion, periodo=periodo, usuario=director)
                print(f'  + boletín {nombre}: id={documento.pk}, versión {documento.version}')
        if not emitidos.filter(periodo__isnull=True).exists():
            documento, _ = boletines.emitir_boletin(historial, gestion, periodo=None, usuario=director)
            print(f'  + boletín anual: id={documento.pk}, versión {documento.version}')

    dispositivos = [
        ('ExponentPushToken[demo-estudiante-0001]', 'ANDROID', True, estudiante_usuario),
        ('ExponentPushToken[demo-tutor-0001]', 'ANDROID', True, tutor_usuario),
        ('ExponentPushToken[demo-director-inactivo]', 'WEB', False, director),
    ]
    creados_disp = 0
    for token, plataforma, activo, usuario in dispositivos:
        _, creado = DispositivoNotificacion.objects.get_or_create(
            token=token, defaults={'usuario': usuario, 'plataforma': plataforma, 'activo': activo},
        )
        if creado:
            creados_disp += 1
    print(f'  + {creados_disp} dispositivos push (2 activos, 1 inactivo)')

    notificaciones = [
        (estudiante_usuario, 'Boletín del Trimestre 1 disponible', 'BOLETIN'),
        (estudiante_usuario, 'Boletín del Trimestre 2 disponible', 'BOLETIN'),
        (estudiante_usuario, 'Boletín del Trimestre 3 disponible', 'BOLETIN'),
        (tutor_usuario, 'Boletín anual de su estudiante disponible', 'BOLETIN'),
    ]
    creadas = 0
    for usuario, titulo, tipo in notificaciones:
        _, creada = Notificacion.objects.get_or_create(
            usuario=usuario, titulo=titulo, tipo=tipo,
            defaults={'mensaje': f'{titulo}. Consulte el detalle desde su portal.'},
        )
        if creada:
            creadas += 1
    print(f'  + {creadas} notificaciones internas de boletín')


def main():
    print('Seed sprint especial (4 ejemplos por funcionalidad)')
    admin = Usuario.objects.get(username='admin')
    director = Usuario.objects.get(username='director')
    profesor_usuario = Usuario.objects.get(username='profesor')
    estudiante_usuario = Usuario.objects.get(username='estudiante')
    tutor_usuario = Usuario.objects.get(username='tutor')
    colegio = Colegio.objects.get(nombre='Colegio Demo SI2')
    unidad = UnidadEducativa.objects.get(codigo_sie='DEMO-SI2-01')

    sembrar_auditoria_hu_se03(admin, director, colegio, unidad)
    sembrar_pagos_qr(admin, colegio)
    sembrar_respaldos(admin, colegio)
    sembrar_boletines_y_notificaciones(unidad, director, profesor_usuario, estudiante_usuario, tutor_usuario)

    print('LISTO. Resumen de ejemplos demo:')
    print(f'  HU-SE03 auditoría: {EventoAuditoria.objects.filter(cambios_sanitizados__contains={"fuente": "seed_demo_sprint_especial"}).count()} eventos sembrados')
    print(f'  Pagos QR: {Pago.objects.filter(qr_id__startswith="demo-qr-").count()} pagos')
    print(f'  Respaldos colegio: {RespaldosCount()}')
    print(f'  Boletines estudiante: {DocumentoAcademicoEmitido.objects.filter(tipo="BOLETIN").count()}')
    print(f'  Dispositivos push: {DispositivoNotificacion.objects.count()} · Notificaciones: {Notificacion.objects.count()}')


def RespaldosCount():
    return Respaldo.objects.filter(alcance=Respaldo.ALCANCE_COLEGIO).count()


if __name__ == '__main__':
    main()

import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, F, Max, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from aplicaciones.estudiantes.models import Estudiante
from aplicaciones.institucion.models import UnidadEducativa

from . import avisos
from .fechas import hoy
from .models import AsignacionBeca, Beca, CuotaPlan, DetallePago, ObligacionPago, Pago, PlanPago

CENTAVO = Decimal('0.01')
MESES = (
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
    'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
)


def _sumar_meses(fecha, meses):
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


def dividir_monto(total, partes):
    """Reparte en partes iguales; la última cuota absorbe el redondeo."""
    base = (total / partes).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    montos = [base] * partes
    montos[-1] = total - base * (partes - 1)
    return montos


def generar_cuotas(plan, fecha_primer_vencimiento):
    if plan.estado != PlanPago.Estado.BORRADOR:
        raise ValidationError({'detail': 'Solo se pueden generar cuotas de un plan en borrador.'})
    with transaction.atomic():
        plan.cuotas.all().delete()
        cuotas = []
        for indice, monto in enumerate(dividir_monto(plan.monto_total, plan.numero_cuotas)):
            vencimiento = _sumar_meses(fecha_primer_vencimiento, indice)
            cuotas.append(CuotaPlan(
                plan=plan, numero=indice + 1, monto=monto, fecha_vencimiento=vencimiento,
                concepto=f'Cuota {indice + 1} - {MESES[vencimiento.month - 1]}',
            ))
        CuotaPlan.objects.bulk_create(cuotas)
    return cuotas


def activar_plan(plan):
    if plan.estado != PlanPago.Estado.BORRADOR:
        raise ValidationError({'detail': 'Solo un plan en borrador puede activarse.'})
    cuotas = list(plan.cuotas.all())
    if len(cuotas) != plan.numero_cuotas:
        raise ValidationError({'detail': 'Genere las cuotas del plan antes de activarlo.'})
    if sum(c.monto for c in cuotas) != plan.monto_total:
        raise ValidationError({'detail': 'La suma de las cuotas no coincide con el monto total.'})
    plan.estado = PlanPago.Estado.ACTIVO
    plan.save(update_fields=['estado', 'updated_at'])


def calcular_descuento(monto, beca):
    if beca is None:
        return Decimal('0.00')
    if beca.tipo_descuento == Beca.TipoDescuento.PORCENTAJE:
        descuento = (monto * beca.valor / 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    else:
        descuento = beca.valor
    return min(descuento, monto)


def beca_vigente(estudiante_id, calendario_id):
    return AsignacionBeca.objects.select_related('beca').filter(
        estudiante_id=estudiante_id, calendario_academico_id=calendario_id,
        estado=AsignacionBeca.Estado.VIGENTE,
    ).first()


def nivel_estudiante(estudiante):
    curso = estudiante.curso
    if curso is None or curso.paralelo_id is None:
        return None
    return curso.paralelo.grado.nivel_educativo


def estudiantes_elegibles(plan, estudiantes):
    """Separa los estudiantes válidos para el plan de los rechazados con motivo."""
    validos, rechazados = [], []
    for estudiante in estudiantes:
        if estudiante.unidad_id != plan.unidad_educativa_id:
            rechazados.append({'estudiante': estudiante.pk, 'motivo': 'Pertenece a otra unidad educativa.'})
        elif not estudiante.estado:
            rechazados.append({'estudiante': estudiante.pk, 'motivo': 'El estudiante está inactivo.'})
        elif plan.nivel_educativo and nivel_estudiante(estudiante) != plan.nivel_educativo:
            rechazados.append({'estudiante': estudiante.pk, 'motivo': 'El nivel del estudiante no corresponde al plan.'})
        else:
            validos.append(estudiante)
    return validos, rechazados


def asignar_plan(plan, estudiantes):
    """Genera las obligaciones del plan para cada estudiante; es idempotente."""
    if plan.estado != PlanPago.Estado.ACTIVO:
        raise ValidationError({'detail': 'Solo un plan activo puede asignarse a estudiantes.'})
    cuotas = list(plan.cuotas.all())
    validos, rechazados = estudiantes_elegibles(plan, estudiantes)
    creadas = omitidas = 0
    with transaction.atomic():
        for estudiante in validos:
            asignacion = beca_vigente(estudiante.pk, plan.calendario_academico_id)
            beca = asignacion.beca if asignacion else None
            for cuota in cuotas:
                descuento = calcular_descuento(cuota.monto, beca)
                _, creada = ObligacionPago.objects.get_or_create(
                    estudiante=estudiante, cuota=cuota,
                    defaults={
                        'asignacion_beca': asignacion, 'monto_original': cuota.monto,
                        'descuento': descuento, 'monto_final': cuota.monto - descuento,
                        'fecha_vencimiento': cuota.fecha_vencimiento,
                        'estado': _estado_por_saldo(cuota.monto - descuento, Decimal('0')),
                    },
                )
                if creada:
                    creadas += 1
                else:
                    omitidas += 1
    return {
        'estudiantes': len(validos), 'obligaciones_creadas': creadas,
        'obligaciones_existentes': omitidas, 'rechazados': rechazados,
    }


def _estado_por_saldo(monto_final, monto_pagado):
    # Una cuota cubierta al 100% por beca no se cobra: queda saldada sin pago.
    return ObligacionPago.Estado.PAGADA if monto_pagado >= monto_final else ObligacionPago.Estado.PENDIENTE


def recalcular_pendientes(estudiante_id, calendario_id):
    """Aplica la beca vigente a las cuotas sin pagos; las que tienen pagos no cambian."""
    asignacion = beca_vigente(estudiante_id, calendario_id)
    beca = asignacion.beca if asignacion else None
    sin_pagos = ObligacionPago.objects.select_for_update().filter(
        estudiante_id=estudiante_id, monto_pagado=0,
        estado__in=(ObligacionPago.Estado.PENDIENTE, ObligacionPago.Estado.PAGADA),
        cuota__plan__calendario_academico_id=calendario_id,
    )
    actualizadas = 0
    for obligacion in sin_pagos:
        descuento = calcular_descuento(obligacion.monto_original, beca)
        obligacion.asignacion_beca = asignacion
        obligacion.descuento = descuento
        obligacion.monto_final = obligacion.monto_original - descuento
        obligacion.estado = _estado_por_saldo(obligacion.monto_final, obligacion.monto_pagado)
        obligacion.save(update_fields=['asignacion_beca', 'descuento', 'monto_final', 'estado', 'updated_at'])
        actualizadas += 1
    return actualizadas


def _siguiente_recibo(unidad_id):
    UnidadEducativa.objects.select_for_update().filter(pk=unidad_id).first()
    ultimo = Pago.objects.filter(unidad_educativa_id=unidad_id).aggregate(maximo=Max('numero_recibo'))['maximo']
    return (ultimo or 0) + 1


def registrar_pago(*, usuario, estudiante, monto, metodo, fecha_pago, referencia='', observaciones='', obligacion_ids=None):
    """HU-24: aplica el monto a las cuotas pendientes, de la más antigua a la más reciente."""
    with transaction.atomic():
        pendientes = ObligacionPago.objects.select_for_update().select_related('cuota__plan').filter(
            estudiante=estudiante, estado=ObligacionPago.Estado.PENDIENTE,
        ).order_by('fecha_vencimiento', 'cuota__numero', 'pk')
        if obligacion_ids:
            pendientes = pendientes.filter(pk__in=obligacion_ids)
        pendientes = [o for o in pendientes if o.saldo > 0]
        if obligacion_ids and len(pendientes) != len(set(obligacion_ids)):
            raise ValidationError({'obligaciones': 'Hay cuotas que no son del estudiante o que ya no tienen saldo.'})
        if not pendientes:
            raise ValidationError({'detail': 'El estudiante no tiene cuotas pendientes de pago.'})
        unidades = {o.cuota.plan.unidad_educativa_id for o in pendientes}
        if len(unidades) != 1:
            raise ValidationError({'obligaciones': 'Registre por separado los pagos de cada unidad educativa.'})
        saldo_total = sum(o.saldo for o in pendientes)
        if monto > saldo_total:
            raise ValidationError({'monto': f'El monto supera el saldo pendiente seleccionado (Bs {saldo_total}).'})

        unidad_id = unidades.pop()
        pago = Pago.objects.create(
            unidad_educativa_id=unidad_id, estudiante=estudiante, numero_recibo=_siguiente_recibo(unidad_id),
            fecha_pago=fecha_pago, monto=monto, metodo=metodo, referencia=referencia,
            observaciones=observaciones, registrado_por=usuario,
        )
        restante = monto
        for obligacion in pendientes:
            if restante <= 0:
                break
            aplicado = min(obligacion.saldo, restante)
            DetallePago.objects.create(pago=pago, obligacion=obligacion, monto=aplicado)
            obligacion.monto_pagado += aplicado
            obligacion.estado = _estado_por_saldo(obligacion.monto_final, obligacion.monto_pagado)
            obligacion.save(update_fields=['monto_pagado', 'estado', 'updated_at'])
            restante -= aplicado
        avisos.avisar_pago(pago)
    return pago


def anular_pago(pago, usuario, motivo):
    """Revierte el pago: las cuotas recuperan el saldo que había cubierto."""
    with transaction.atomic():
        pago = Pago.objects.select_for_update().get(pk=pago.pk)
        if pago.estado == Pago.Estado.ANULADO:
            raise ValidationError({'detail': 'El pago ya fue anulado.'})
        for detalle in pago.detalles.select_related('obligacion'):
            obligacion = ObligacionPago.objects.select_for_update().get(pk=detalle.obligacion_id)
            obligacion.monto_pagado -= detalle.monto
            if obligacion.estado != ObligacionPago.Estado.ANULADA:
                obligacion.estado = _estado_por_saldo(obligacion.monto_final, obligacion.monto_pagado)
            obligacion.save(update_fields=['monto_pagado', 'estado', 'updated_at'])
        pago.estado = Pago.Estado.ANULADO
        pago.motivo_anulacion = motivo
        pago.anulado_por = usuario
        pago.anulado_at = timezone.now()
        pago.save(update_fields=['estado', 'motivo_anulacion', 'anulado_por', 'anulado_at'])
        avisos.avisar_pago_anulado(pago)
    return pago


def _vencidas(queryset, hoy):
    return queryset.filter(
        estado=ObligacionPago.Estado.PENDIENTE, fecha_vencimiento__lt=hoy, monto_final__gt=F('monto_pagado'),
    )


def estado_cuenta(estudiante, obligaciones, pagos):
    """HU-24: resumen de cargos, descuentos, pagos y saldos de un estudiante."""
    fecha_hoy = hoy()
    vigentes = obligaciones.exclude(estado=ObligacionPago.Estado.ANULADA)
    totales = vigentes.aggregate(
        cargos=Sum('monto_original'), descuentos=Sum('descuento'),
        a_pagar=Sum('monto_final'), pagado=Sum('monto_pagado'),
    )
    vencido = _vencidas(vigentes, fecha_hoy).aggregate(total=Sum(F('monto_final') - F('monto_pagado')))['total']
    cero = Decimal('0.00')
    a_pagar, pagado = totales['a_pagar'] or cero, totales['pagado'] or cero
    proxima = vigentes.filter(
        estado=ObligacionPago.Estado.PENDIENTE, fecha_vencimiento__gte=fecha_hoy,
    ).order_by('fecha_vencimiento').first()
    return {
        'estudiante': estudiante.pk,
        'resumen': {
            'total_cargos': totales['cargos'] or cero, 'total_descuentos': totales['descuentos'] or cero,
            'total_a_pagar': a_pagar, 'total_pagado': pagado, 'saldo_pendiente': a_pagar - pagado,
            'saldo_vencido': vencido or cero,
            'proximo_vencimiento': proxima.fecha_vencimiento if proxima else None,
            'proximo_monto': proxima.saldo if proxima else None,
        },
        'obligaciones': obligaciones,
        'pagos': pagos,
    }


TRAMOS_MORA = (('1-30', 1, 30), ('31-60', 31, 60), ('61-90', 61, 90), ('90+', 91, None))


def tramo_mora(dias):
    for nombre, minimo, maximo in TRAMOS_MORA:
        if dias >= minimo and (maximo is None or dias <= maximo):
            return nombre
    return None


def morosidad(obligaciones, dias_minimos=1):
    """HU-26: estudiantes con cuotas vencidas, agrupados por antigüedad de la deuda."""
    fecha_hoy = hoy()
    vigentes = obligaciones.exclude(estado=ObligacionPago.Estado.ANULADA)
    exigible = vigentes.filter(fecha_vencimiento__lt=fecha_hoy).aggregate(total=Sum('monto_final'))['total'] or Decimal('0')
    filas = {}
    for o in _vencidas(vigentes, fecha_hoy).select_related('estudiante__usuario', 'estudiante__curso').order_by('fecha_vencimiento'):
        fila = filas.setdefault(o.estudiante_id, {
            'estudiante': o.estudiante_id,
            'estudiante_nombre': f'{o.estudiante.usuario.nombre} {o.estudiante.usuario.apellido}'.strip(),
            'curso_nombre': o.estudiante.curso.nombre if o.estudiante.curso else None,
            'cuotas_vencidas': 0, 'monto_vencido': Decimal('0'), 'vencimiento_mas_antiguo': o.fecha_vencimiento,
        })
        fila['cuotas_vencidas'] += 1
        fila['monto_vencido'] += o.saldo
    resultado = []
    for fila in filas.values():
        fila['dias_mora'] = (fecha_hoy - fila['vencimiento_mas_antiguo']).days
        fila['tramo'] = tramo_mora(fila['dias_mora'])
        if fila['dias_mora'] >= dias_minimos:
            resultado.append(fila)
    resultado.sort(key=lambda f: (-f['dias_mora'], -f['monto_vencido']))
    monto_vencido = sum((f['monto_vencido'] for f in resultado), Decimal('0'))
    estudiantes_con_cuotas = vigentes.values('estudiante_id').distinct().count()
    por_tramo = {nombre: {'estudiantes': 0, 'monto': Decimal('0')} for nombre, _, _ in TRAMOS_MORA}
    for fila in resultado:
        por_tramo[fila['tramo']]['estudiantes'] += 1
        por_tramo[fila['tramo']]['monto'] += fila['monto_vencido']
    return {
        'fecha_corte': fecha_hoy,
        'resumen': {
            'estudiantes_morosos': len(resultado), 'estudiantes_con_cuotas': estudiantes_con_cuotas,
            'monto_vencido': monto_vencido, 'monto_exigible': exigible,
            'indice_morosidad': (monto_vencido / exigible * 100).quantize(CENTAVO) if exigible else Decimal('0.00'),
            'por_tramo': [{'tramo': nombre, **valores} for nombre, valores in por_tramo.items()],
        },
        'estudiantes': resultado,
    }


def simulacion_tributaria(pagos, obligaciones, desde, hasta, tasa_iva, tasa_it, credito_fiscal):
    """HU-26: estima IVA e IT sobre lo cobrado y lo proyectado en un rango de fechas.

    Es una simulación: el IVA va incluido en el precio (débito = tasa sobre el total
    facturado) y el IT se calcula sobre el ingreso bruto. No sustituye la
    liquidación oficial ante Impuestos Nacionales.
    """
    def impuestos(base):
        debito = (base * tasa_iva / 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        it = (base * tasa_it / 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        iva_a_pagar = max(debito - credito_fiscal, Decimal('0.00'))
        return {
            'base_imponible': base, 'debito_fiscal_iva': debito, 'credito_fiscal': credito_fiscal,
            'iva_a_pagar': iva_a_pagar, 'saldo_a_favor': max(credito_fiscal - debito, Decimal('0.00')),
            'it': it, 'total_impuestos': iva_a_pagar + it, 'ingreso_neto': base - iva_a_pagar - it,
        }

    cobrados = pagos.filter(estado=Pago.Estado.VALIDO, fecha_pago__range=(desde, hasta))
    cobrado = cobrados.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    proyectado = obligaciones.filter(
        estado=ObligacionPago.Estado.PENDIENTE, fecha_vencimiento__range=(desde, hasta),
    ).aggregate(total=Sum(F('monto_final') - F('monto_pagado')))['total'] or Decimal('0.00')
    mensual = [
        {'mes': fila['mes'].strftime('%Y-%m'), 'cobrado': fila['total'], 'pagos': fila['cantidad']}
        for fila in cobrados.annotate(mes=TruncMonth('fecha_pago')).values('mes').annotate(
            total=Sum('monto'), cantidad=Count('pk'),
        ).order_by('mes')
    ]
    return {
        'desde': desde, 'hasta': hasta, 'tasa_iva': tasa_iva, 'tasa_it': tasa_it,
        'cobrado': impuestos(cobrado),
        'proyectado': {'pendiente_por_cobrar': proyectado, **impuestos(cobrado + proyectado)},
        'mensual': mensual,
    }


def estudiantes_por_ids_o_curso(plan, ids=None, curso_id=None):
    queryset = Estudiante.objects.select_related('curso__paralelo__grado')
    if ids:
        return list(queryset.filter(pk__in=ids))
    return list(queryset.filter(curso_id=curso_id, unidad_id=plan.unidad_educativa_id))

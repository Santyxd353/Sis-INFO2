import axiosInstance from './axiosInstance'
import type { PaginatedResponse } from './types'

export type EstadoPlan = 'BORRADOR' | 'ACTIVO' | 'INACTIVO'
export type NivelEducativo = 'INI' | 'PRI' | 'SEC'
export type TipoDescuento = 'PORCENTAJE' | 'MONTO_FIJO'
export type EstadoObligacion = 'PENDIENTE' | 'PAGADA' | 'ANULADA'

export interface CuotaPlan { id: number; numero: number; concepto: string; monto: string; fecha_vencimiento: string }

export interface PlanPago {
  id: number
  unidad_educativa: number
  unidad_nombre: string
  calendario_academico: number
  gestion: number
  nombre: string
  descripcion: string
  nivel_educativo: NivelEducativo | null
  nivel_display: string | null
  monto_total: string
  numero_cuotas: number
  moneda: string
  estado: EstadoPlan
  cuotas: CuotaPlan[]
  estudiantes_asignados: number
}

export interface Beca {
  id: number
  unidad_educativa: number
  unidad_nombre: string
  nombre: string
  descripcion: string
  tipo_descuento: TipoDescuento
  tipo_descuento_display: string
  valor: string
  estado: 'ACTIVO' | 'INACTIVO'
  asignaciones_vigentes: number
}

export interface AsignacionBeca {
  id: number
  beca: number
  beca_nombre: string
  tipo_descuento: TipoDescuento
  valor: string
  estudiante: number
  estudiante_nombre: string
  curso_nombre: string | null
  calendario_academico: number
  gestion: number
  motivo: string
  estado: 'VIGENTE' | 'REVOCADA'
  asignado_por_nombre: string
  motivo_revocacion: string
  created_at: string
}

export interface ObligacionPago {
  id: number
  estudiante: number
  estudiante_nombre: string
  curso_nombre: string | null
  plan: number
  plan_nombre: string
  gestion: number
  numero_cuota: number
  concepto: string
  monto_original: string
  descuento: string
  monto_final: string
  monto_pagado: string
  saldo: string
  beca_nombre: string | null
  fecha_vencimiento: string
  estado: EstadoObligacion
  vencida: boolean
  motivo_anulacion: string
}

export interface EstudianteElegible { id: number; nombre: string; rude: string; curso: number | null; curso_nombre: string | null }

export interface ResultadoAsignacion {
  estudiantes: number
  obligaciones_creadas: number
  obligaciones_existentes: number
  rechazados: { estudiante: number; motivo: string }[]
}

export type DatosPlan = Pick<PlanPago, 'unidad_educativa' | 'calendario_academico' | 'nombre' | 'descripcion' | 'monto_total' | 'numero_cuotas'> & { nivel_educativo: NivelEducativo | null }
export type DatosBeca = Pick<Beca, 'unidad_educativa' | 'nombre' | 'descripcion' | 'tipo_descuento' | 'valor'>
export type Filtros = Record<string, string | number | boolean | undefined>

const params = (data: Filtros) => Object.fromEntries(
  Object.entries(data).filter(([, value]) => value !== undefined && value !== null && value !== ''),
)
const BASE = '/finanzas'

export const listarPlanes = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<PaginatedResponse<PlanPago>>(`${BASE}/planes-pago/`, { params: params(filtros), signal })
export const crearPlan = (datos: DatosPlan) => axiosInstance.post<PlanPago>(`${BASE}/planes-pago/`, datos)
export const actualizarPlan = (id: number, datos: Partial<DatosPlan>) => axiosInstance.patch<PlanPago>(`${BASE}/planes-pago/${id}/`, datos)
export const generarCuotas = (id: number, fecha_primer_vencimiento: string) =>
  axiosInstance.post<PlanPago>(`${BASE}/planes-pago/${id}/generar-cuotas/`, { fecha_primer_vencimiento })
export const activarPlan = (id: number) => axiosInstance.post<PlanPago>(`${BASE}/planes-pago/${id}/activar/`)
export const desactivarPlan = (id: number) => axiosInstance.post<PlanPago>(`${BASE}/planes-pago/${id}/desactivar/`)
export const asignarPlan = (id: number, destino: { curso: number } | { estudiantes: number[] }) =>
  axiosInstance.post<ResultadoAsignacion>(`${BASE}/planes-pago/${id}/asignar/`, destino)

export const listarBecas = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<PaginatedResponse<Beca>>(`${BASE}/becas/`, { params: params(filtros), signal })
export const crearBeca = (datos: DatosBeca) => axiosInstance.post<Beca>(`${BASE}/becas/`, datos)
export const actualizarBeca = (id: number, datos: Partial<DatosBeca>) => axiosInstance.patch<Beca>(`${BASE}/becas/${id}/`, datos)
export const cambiarEstadoBeca = (id: number, activar: boolean) =>
  axiosInstance.post<Beca>(`${BASE}/becas/${id}/${activar ? 'activar' : 'desactivar'}/`)

export const listarAsignacionesBeca = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<PaginatedResponse<AsignacionBeca>>(`${BASE}/asignaciones-beca/`, { params: params(filtros), signal })
export const otorgarBeca = (datos: { beca: number; estudiante: number; calendario_academico: number; motivo: string }) =>
  axiosInstance.post<AsignacionBeca>(`${BASE}/asignaciones-beca/`, datos)
export const revocarBeca = (id: number, motivo: string) =>
  axiosInstance.post<AsignacionBeca>(`${BASE}/asignaciones-beca/${id}/revocar/`, { motivo })
export const buscarEstudiantes = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<EstudianteElegible[]>(`${BASE}/asignaciones-beca/estudiantes/`, { params: params(filtros), signal })

export const listarObligaciones = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<PaginatedResponse<ObligacionPago>>(`${BASE}/obligaciones/`, { params: params(filtros), signal })
export const anularObligacion = (id: number, motivo: string) =>
  axiosInstance.post<ObligacionPago>(`${BASE}/obligaciones/${id}/anular/`, { motivo })

export type MetodoPago = 'EFECTIVO' | 'TRANSFERENCIA' | 'QR' | 'TARJETA'
export const METODOS_PAGO: [MetodoPago, string][] = [['EFECTIVO', 'Efectivo'], ['TRANSFERENCIA', 'Transferencia bancaria'], ['QR', 'Pago QR'], ['TARJETA', 'Tarjeta']]

export interface Pago {
  id: number
  estudiante: number
  estudiante_nombre: string
  curso_nombre: string | null
  numero_recibo: number
  fecha_pago: string
  monto: string
  metodo: MetodoPago
  metodo_display: string
  referencia: string
  observaciones: string
  estado: 'VALIDO' | 'ANULADO'
  registrado_por_nombre: string
  motivo_anulacion: string
  detalles: { id: number; obligacion: number; concepto: string; plan_nombre: string; monto: string }[]
}

export interface DatosPago {
  estudiante: number
  monto: string
  metodo: MetodoPago
  fecha_pago?: string
  referencia?: string
  observaciones?: string
  obligaciones?: number[]
}

type Monto = string | number
export interface EstadoCuenta {
  estudiante: number
  estudiante_nombre: string
  rude: string
  curso_nombre: string | null
  resumen: {
    total_cargos: Monto; total_descuentos: Monto; total_a_pagar: Monto; total_pagado: Monto
    saldo_pendiente: Monto; saldo_vencido: Monto; proximo_vencimiento: string | null; proximo_monto: Monto | null
  }
  obligaciones: ObligacionPago[]
  pagos: Pago[]
}

export interface FilaMorosidad {
  estudiante: number
  estudiante_nombre: string
  curso_nombre: string | null
  cuotas_vencidas: number
  monto_vencido: Monto
  vencimiento_mas_antiguo: string
  dias_mora: number
  tramo: string
}

export interface Morosidad {
  fecha_corte: string
  resumen: {
    estudiantes_morosos: number; estudiantes_con_cuotas: number; monto_vencido: Monto; monto_exigible: Monto
    indice_morosidad: Monto; por_tramo: { tramo: string; estudiantes: number; monto: Monto }[]
  }
  estudiantes: FilaMorosidad[]
}

export interface Impuestos {
  base_imponible: Monto; debito_fiscal_iva: Monto; credito_fiscal: Monto; iva_a_pagar: Monto
  saldo_a_favor: Monto; it: Monto; total_impuestos: Monto; ingreso_neto: Monto
}

export interface SimulacionTributaria {
  desde: string
  hasta: string
  tasa_iva: Monto
  tasa_it: Monto
  cobrado: Impuestos
  proyectado: Impuestos & { pendiente_por_cobrar: Monto }
  mensual: { mes: string; cobrado: Monto; pagos: number }[]
}

export const listarPagos = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<PaginatedResponse<Pago>>(`${BASE}/pagos/`, { params: params(filtros), signal })
export const registrarPago = (datos: DatosPago) => axiosInstance.post<Pago>(`${BASE}/pagos/`, datos)
export const anularPago = (id: number, motivo: string) => axiosInstance.post<Pago>(`${BASE}/pagos/${id}/anular/`, { motivo })
export const abrirRecibo = async (pago: Pick<Pago, 'id' | 'numero_recibo'>) => {
  const { data } = await axiosInstance.get<Blob>(`${BASE}/pagos/${pago.id}/recibo/`, { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = `recibo-${String(pago.numero_recibo).padStart(6, '0')}.pdf`
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
}

export const obtenerEstadoCuenta = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<EstadoCuenta>(`${BASE}/estado-cuenta/`, { params: params(filtros), signal })
export const obtenerMorosidad = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<Morosidad>(`${BASE}/morosidad/`, { params: params(filtros), signal })
export const simularTributos = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<SimulacionTributaria>(`${BASE}/simulacion-tributaria/`, { params: params(filtros), signal })

export type EstadoSolicitudQR = 'PENDIENTE' | 'PAGADA' | 'EXPIRADA' | 'OBSERVADA' | 'ANULADA'
export interface SolicitudQR {
  id: number
  estudiante: number
  estudiante_nombre: string
  curso_nombre: string | null
  conceptos: string[]
  monto: string
  qr_id: string | null
  qr_url: string
  simulado: boolean
  expira_at: string
  estado: EstadoSolicitudQR
  conciliacion: EstadoSolicitudQR | 'CONCILIADA' | 'DESCUADRE'
  pago: number | null
  numero_recibo: number | null
  monto_reportado: string | null
  observacion: string
  solicitado_por_nombre: string
  created_at: string
}

export interface ConciliacionQR {
  modo_simulado: boolean
  resumen: {
    cobrado_pasarela: Monto; registrado_sistema: Monto; diferencia: Monto; conciliadas: number; descuadres: number
    observadas: number; pendientes: number; expiradas: number; pagos_qr_sin_respaldo: number; monto_qr_sin_respaldo: Monto
  }
  por_resolver: SolicitudQR[]
}

export const listarSolicitudesQR = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<PaginatedResponse<SolicitudQR>>(`${BASE}/solicitudes-qr/`, { params: params(filtros), signal })
export const crearSolicitudQR = (datos: { estudiante: number; obligaciones?: number[] }) =>
  axiosInstance.post<SolicitudQR>(`${BASE}/solicitudes-qr/`, datos)
export const verificarSolicitudQR = (id: number) => axiosInstance.post<SolicitudQR>(`${BASE}/solicitudes-qr/${id}/verificar/`)
export const anularSolicitudQR = (id: number, motivo: string) =>
  axiosInstance.post<SolicitudQR>(`${BASE}/solicitudes-qr/${id}/anular/`, { motivo })
export const resolverSolicitudQR = (id: number, accion: 'aplicar' | 'descartar', motivo: string) =>
  axiosInstance.post<SolicitudQR>(`${BASE}/solicitudes-qr/${id}/resolver/`, { accion, motivo })
export const simularCobroQR = (id: number) => axiosInstance.post<SolicitudQR>(`${BASE}/solicitudes-qr/${id}/simular-cobro/`)
export const obtenerConciliacionQR = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<ConciliacionQR>(`${BASE}/conciliacion-qr/`, { params: params(filtros), signal })

export const formatoMonto = (valor: string | number, moneda = 'BOB') =>
  `${moneda === 'BOB' ? 'Bs' : moneda} ${Number(valor).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export type TipoRecordatorio = 'VENCIDAS' | 'POR_VENCER'
export interface ResultadoRecordatorios { estudiantes_avisados: number; ya_avisados_hoy: number }
export interface RecordatorioPago {
  id: number
  estudiante: number
  estudiante_nombre: string
  tipo: TipoRecordatorio
  tipo_display: string
  fecha: string
  monto: Monto
  created_at: string
}

export const enviarRecordatoriosPago = (datos: { tipo: TipoRecordatorio; dias?: number; unidad_educativa?: number; curso?: number }) =>
  axiosInstance.post<ResultadoRecordatorios>(`${BASE}/recordatorios-pago/`, datos)
export const listarRecordatoriosPago = (filtros: Filtros, signal?: AbortSignal) =>
  axiosInstance.get<RecordatorioPago[]>(`${BASE}/recordatorios-pago/`, { params: params(filtros), signal })

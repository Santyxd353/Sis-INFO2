import axiosInstance from './axiosInstance'
import { normalizeCollection } from './types'

export interface Plan {
  id: number
  nombre: string
  descripcion: string
  precio: string
  moneda: string
  periodicidad: 'MENSUAL' | 'TRIMESTRAL' | 'SEMESTRAL' | 'ANUAL'
  periodicidad_display: string
  modulos_habilitados: string[]
  limite_usuarios: number
  limite_unidades: number
  estado: 'ACTIVO' | 'INACTIVO'
  estado_display: string
  qr_simulado_disponible?: boolean
  created_at: string
  updated_at: string
}

export interface PlanPayload {
  nombre: string
  descripcion?: string
  precio: string
  moneda?: string
  periodicidad: string
  modulos_habilitados?: string[]
  limite_usuarios?: number
  limite_unidades?: number
  estado?: string
}

export interface Suscripcion {
  id: number
  colegio: number
  colegio_nombre: string
  plan: number
  plan_nombre: string
  precio_periodico: string
  moneda: string
  periodicidad: string
  periodicidad_display: string
  modulos_habilitados: string[]
  limite_usuarios: number
  limite_unidades: number
  fecha_inicio: string
  fecha_vencimiento: string
  estado: 'PENDIENTE' | 'ACTIVA' | 'VENCIDA' | 'SUSPENDIDA' | 'CANCELADA'
  estado_display: string
  estado_efectivo: string
  qr_simulado_disponible?: boolean
  created_at: string
  updated_at: string
}

export interface ContratarSuscripcionPayload {
  plan: number
  colegio?: number
  fecha_inicio?: string
}

export interface Pago {
  id: number
  suscripcion: number
  suscripcion_colegio_nombre: string
  suscripcion_plan_nombre: string
  metodo: MetodoPago['codigo']
  metodo_display: string
  referencia: string
  monto: string
  moneda: string
  fecha: string
  resultado: 'PENDIENTE' | 'VALIDADO' | 'RECHAZADO'
  resultado_display: string
  observacion: string
  validado_por: number | null
  validado_por_nombre: string | null
  validado_at: string | null
  qr_id: string | null
  qr_url: string
  qr_expira_at: string | null
  qr_imagen_simulada?: string
  created_at: string
  updated_at: string
}

export interface PagoPayload {
  suscripcion: number
  metodo: string
  referencia: string
  monto: string | number
  moneda?: string
  fecha?: string
  observacion?: string
}

export interface MetodoPago {
  id: number
  codigo: 'TRANSFERENCIA' | 'TARJETA' | 'EFECTIVO' | 'PASARELA' | 'STRIPE' | 'QR_SIMULADO'
  nombre: string
  descripcion: string
  activo: boolean
  modo_prueba?: boolean
  disponible?: boolean
  creado_at: string
  actualizado_at: string
}

export interface MetodoPagoPayload {
  codigo: MetodoPago['codigo']
  nombre: string
  descripcion?: string
  activo?: boolean
}

export interface EstadoSuscripcion {
  tiene_suscripcion: boolean
  suscripcion: number | null
  plan: string | null
  estado: string
  estado_display: string | null
  fecha_inicio: string | null
  fecha_vencimiento: string | null
  precio_periodico: string | null
  moneda: string | null
  periodicidad: string | null
  periodicidad_display: string | null
  modulos_habilitados: string[]
  limite_usuarios: number | null
  limite_unidades: number | null
  suscripcion_activa: boolean
  restriccion: string | null
}

export interface ColegioCatalogo {
  id: number
  nombre: string
}

export const listarPlanes = (params: { estado?: string } = {}) =>
  axiosInstance.get<Plan[] | { count: number; results: Plan[] }>('/suscripciones/planes/', { params })

export const crearPlan = (payload: PlanPayload) =>
  axiosInstance.post<Plan>('/suscripciones/planes/', payload)

export const editarPlan = (id: number, payload: Partial<PlanPayload>) =>
  axiosInstance.patch<Plan>(`/suscripciones/planes/${id}/`, payload)

export const eliminarPlan = (id: number) =>
  axiosInstance.delete(`/suscripciones/planes/${id}/`)

export const listarSuscripciones = (params: { colegio?: string; estado?: string } = {}) =>
  axiosInstance.get<Suscripcion[] | { count: number; results: Suscripcion[] }>('/suscripciones/suscripciones/', { params })

export const contratarPlan = (payload: ContratarSuscripcionPayload) =>
  axiosInstance.post<Suscripcion>('/suscripciones/suscripciones/', payload)

export const suspenderSuscripcion = (id: number) =>
  axiosInstance.post<Suscripcion>(`/suscripciones/suscripciones/${id}/suspender/`)

export const cancelarSuscripcion = (id: number) =>
  axiosInstance.post<Suscripcion>(`/suscripciones/suscripciones/${id}/cancelar/`)

export const reactivarSuscripcion = (id: number) =>
  axiosInstance.post<Suscripcion>(`/suscripciones/suscripciones/${id}/reactivar/`)

export const obtenerEstadoSuscripcion = () =>
  axiosInstance.get<EstadoSuscripcion>('/suscripciones/suscripciones/mi-estado/')

export const listarPagos = (
  params: { colegio?: string; suscripcion?: string; resultado?: string } = {},
) =>
  axiosInstance.get<Pago[] | { count: number; results: Pago[] }>('/suscripciones/pagos/', { params })

export const registrarPago = (payload: PagoPayload) =>
  axiosInstance.post<Pago>('/suscripciones/pagos/', payload)

export const listarMetodosPago = () => axiosInstance.get<MetodoPago[]>('/suscripciones/metodos-pago/')
export const listarMetodosPagoPublicos = () => axiosInstance.get<MetodoPago[]>('/suscripciones/metodos-pago-publicos/')
export const crearMetodoPago = (payload: MetodoPagoPayload) => axiosInstance.post<MetodoPago>('/suscripciones/metodos-pago/', payload)
export const editarMetodoPago = (id: number, payload: Partial<MetodoPagoPayload>) => axiosInstance.patch<MetodoPago>(`/suscripciones/metodos-pago/${id}/`, payload)

export const generarQr = (id: number) => axiosInstance.post<Pago>(`/suscripciones/suscripciones/${id}/generar-qr/`, undefined, { timeout: 35000 })
export const generarQrSimulado = (id: number) => axiosInstance.post<Pago>(`/suscripciones/suscripciones/${id}/generar-qr-simulado/`)
export const simularPagoQr = (id: number) => axiosInstance.post<Pago>(`/suscripciones/pagos/${id}/simular-pago-qr/`, undefined, { timeout: 20000 })
export const iniciarCheckoutStripe = (id: number) =>
  axiosInstance.post<{ checkout_url: string }>(`/suscripciones/suscripciones/${id}/checkout-stripe/`, undefined, { timeout: 35000 })

export function urlCheckoutStripe(url?: string): string | undefined {
  if (!url) return
  try {
    const destino = new URL(url)
    if (destino.origin === 'https://checkout.stripe.com' && !destino.username && !destino.password) return destino.href
  } catch { /* Una URL inválida no permite continuar el pago. */ }
}
export const consultarQr = (id: number) => axiosInstance.post<Pago>(`/suscripciones/pagos/${id}/consultar-qr/`, undefined, { timeout: 35000 })

export const validarPago = (id: number) =>
  axiosInstance.post<Pago>(`/suscripciones/pagos/${id}/validar/`)

export const rechazarPago = (id: number, motivo: string) =>
  axiosInstance.post<Pago>(`/suscripciones/pagos/${id}/rechazar/`, { motivo })

export const listarColegiosCatalogo = async (): Promise<ColegioCatalogo[]> =>
  normalizeCollection<ColegioCatalogo>(
    (await axiosInstance.get<ColegioCatalogo[] | { count: number; results: ColegioCatalogo[] }>('/institucion/colegios/')).data,
  )

export const normalizarPlanes = (data: Plan[] | { count: number; results: Plan[] }): Plan[] =>
  normalizeCollection(data)

export const normalizarSuscripciones = (
  data: Suscripcion[] | { count: number; results: Suscripcion[] },
): Suscripcion[] => normalizeCollection(data)

export const normalizarPagos = (
  data: Pago[] | { count: number; results: Pago[] },
): Pago[] => normalizeCollection(data)

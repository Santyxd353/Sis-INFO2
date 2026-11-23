import api from './axiosInstance'

export type AlcanceRespaldo = 'GLOBAL' | 'COLEGIO'
export type EstadoRespaldo = 'PENDIENTE' | 'EJECUTANDO' | 'COMPLETADO' | 'FALLIDO' | 'ARCHIVADO'

export interface Respaldo {
  id: string
  alcance: AlcanceRespaldo
  colegio: number | null
  colegio_nombre?: string | null
  origen: 'MANUAL' | 'PROGRAMADO'
  estado: EstadoRespaldo | string
  solicitado_at: string
  iniciado_at: string | null
  finalizado_at: string | null
  tamano: number | null
  sha256?: string
  version_formato?: number
  metadatos?: Record<string, unknown>
  error: string
}

export interface ConfiguracionRespaldo {
  activo: boolean
  hora: string
  zona_horaria: string
  ultima_fecha_programada: string | null
}

export interface ColegioCatalogo { id: number; nombre: string }

export const listarRespaldos = () => api.get<Respaldo[]>('/respaldos/')
export const obtenerRespaldo = (id: string) => api.get<Respaldo>(`/respaldos/${id}/`)
export const crearRespaldo = (alcance: AlcanceRespaldo, colegio?: number) =>
  alcance === 'GLOBAL' ? api.post<Respaldo>('/respaldos/') : api.post<Respaldo>('/respaldos/', { alcance, colegio })
export const descargarRespaldo = (id: string) =>
  api.get<Blob>(`/respaldos/${id}/descargar/`, { responseType: 'blob', timeout: 120000 })
export const obtenerConfiguracionRespaldo = () => api.get<ConfiguracionRespaldo>('/respaldos/configuracion/')
export const guardarConfiguracionRespaldo = (config: ConfiguracionRespaldo) => api.put<ConfiguracionRespaldo>('/respaldos/configuracion/', config)
export const obtenerEstadoProcesador = () => api.get<{ estado: 'DISPONIBLE' | 'NO_DISPONIBLE'; ultima_actividad: string | null }>('/respaldos/estado-procesador/')

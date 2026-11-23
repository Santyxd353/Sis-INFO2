import axiosInstance from './axiosInstance'
import type { PaginatedResponse } from './types'

export interface EventoAuditoria {
  id: number
  ambito: string
  colegio: number | null
  unidad_educativa: number | null
  usuario: number | null
  actor_snapshot: string | null
  actor_username: string | null
  actor_rol: string | null
  accion: string
  entidad: string
  entidad_id: string | null
  cambios_sanitizados: Record<string, unknown> | null
  ip_hash: string | null
  correlacion: string
  fecha_cliente: string | null
  zona_cliente: string | null
  created_at: string
}

export interface FiltrosAuditoria {
  usuario?: number | string
  accion?: string
  entidad?: string
  colegio?: number | string
  unidad?: number | string
  desde?: string
  hasta?: string
  page?: number
  page_size?: number
}

const parametros = (filtros: FiltrosAuditoria) => Object.fromEntries(
  Object.entries(filtros).filter(([, valor]) => valor !== undefined && valor !== null && valor !== ''),
)

export const listarAuditoria = (params: FiltrosAuditoria, signal?: AbortSignal) =>
  axiosInstance.get<PaginatedResponse<EventoAuditoria>>('/usuarios/auditoria/', {
    params: parametros(params), signal,
  })

export const obtenerEventoAuditoria = (id: number) =>
  axiosInstance.get<EventoAuditoria>(`/usuarios/auditoria/${id}/`)


import api from './axiosInstance'
import type { PaginatedResponse } from './types'

export type EstadoInfraestructura = 'ACTIVO' | 'INACTIVO'
export type TipoAula = 'AUL' | 'LAB' | 'TAL' | 'AUD' | 'COM' | 'GIM' | 'BIB'

export interface ModuloFisico {
  id: number
  nombre: string
  cantidad_aulas: number
  descripcion: string | null
  pisos: number
  unidad_educativa: number | null
  colegio_id: number | null
  estado: EstadoInfraestructura
  created_at: string | null
  updated_at: string | null
}

export interface AulaFisica {
  id: number
  modulo: number | null
  nombre: string
  capacidad: number
  estado: boolean
  tipo: TipoAula
  equipamiento: string | null
  piso: number
  unidad_educativa_id: number | null
  colegio_id: number | null
  created_at: string | null
  updated_at: string | null
}

export interface FiltrosInfraestructura {
  unidad_educativa?: number
  colegio?: number
  modulo?: number
  estado?: EstadoInfraestructura | 'ACTIVO' | 'INACTIVO'
  tipo?: TipoAula
  nombre?: string
  page?: number
  page_size?: number
}

export interface ModuloPayload {
  unidad_educativa: number
  nombre: string
  cantidad_aulas: number
  descripcion?: string
  pisos: number
}

export interface AulaPayload {
  modulo: number
  nombre: string
  capacidad: number
  tipo: TipoAula
  piso: number
  equipamiento?: string
}

const clean = <T extends object>(filters: T) => Object.fromEntries(
  Object.entries(filters).filter(([, value]) => value !== undefined && value !== null && value !== ''),
) as T

export const listarModulos = (filtros: FiltrosInfraestructura, signal?: AbortSignal) =>
  api.get<PaginatedResponse<ModuloFisico>>('/institucion/modulos/', { params: clean(filtros), signal })

export const crearModulo = (datos: ModuloPayload) => api.post<ModuloFisico>('/institucion/modulos/', datos)
export const actualizarModulo = (id: number, datos: Partial<ModuloPayload>) => api.patch<ModuloFisico>(`/institucion/modulos/${id}/`, datos)
export const desactivarModulo = (id: number) => api.post<ModuloFisico>(`/institucion/modulos/${id}/desactivar/`)

export const listarAulas = (filtros: FiltrosInfraestructura, signal?: AbortSignal) =>
  api.get<PaginatedResponse<AulaFisica>>('/institucion/aulas/', { params: clean(filtros), signal })

export const crearAula = (datos: AulaPayload) => api.post<AulaFisica>('/institucion/aulas/', datos)
export const actualizarAula = (id: number, datos: Partial<AulaPayload>) => api.patch<AulaFisica>(`/institucion/aulas/${id}/`, datos)
export const desactivarAula = (id: number) => api.post<AulaFisica>(`/institucion/aulas/${id}/desactivar/`)

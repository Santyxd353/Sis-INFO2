import axiosInstance from './axiosInstance'
import { normalizeCollection, type PaginatedResponse } from './types'

export type NivelEvaluacion = 'INI' | 'PRI' | 'SEC'
export type ReglaRedondeo = 'NORMAL' | 'TRUNCAR' | 'SUPERIOR'

export interface DimensionEvaluacion {
  id: number
  codigo: string
  nombre: string
  ponderacion: string
  orden: number
  estado: string
}

export interface ConfiguracionEvaluacion {
  id: number
  calendario_academico: number
  gestion_anio: number | null
  unidad_educativa: number
  unidad_nombre: string
  nivel: NivelEvaluacion
  nivel_display: string
  nota_minima: string
  nota_maxima: string
  nota_aprobacion: string
  decimales: number
  regla_redondeo: ReglaRedondeo
  estado: string
  dimensiones: DimensionEvaluacion[]
  created_at: string
  updated_at: string
}

export interface DimensionPayload {
  codigo: string
  nombre: string
  ponderacion: string
  orden: number
}

export interface ConfigurarEvaluacionPayload {
  calendario_academico: number
  nivel: NivelEvaluacion
  nota_minima: string
  nota_maxima: string
  nota_aprobacion: string
  decimales: number
  regla_redondeo: ReglaRedondeo
  dimensiones: DimensionPayload[]
}

export interface Calendario { id: number; unidad_educativa: number; unidad_nombre: string; año: number; activo: boolean }

export const listarConfiguracionesEvaluacion = (params: { calendario_academico?: number; nivel?: string } = {}) =>
  axiosInstance.get<PaginatedResponse<ConfiguracionEvaluacion> | ConfiguracionEvaluacion[]>(
    '/academico/configuraciones-evaluacion/', { params },
  )

export const configurarDimensionesEvaluacion = (payload: ConfigurarEvaluacionPayload) =>
  axiosInstance.put<ConfiguracionEvaluacion>('/academico/configuraciones-evaluacion/configurar/', payload)

const obtenerCatalogo = async <T>(url: string) =>
  normalizeCollection((await axiosInstance.get<T[] | PaginatedResponse<T>>(url)).data)

export const listarCalendarios = () => obtenerCatalogo<Calendario>('/calendario/calendarios/')

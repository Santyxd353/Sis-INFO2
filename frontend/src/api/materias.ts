import axiosInstance from './axiosInstance'
import type { PaginatedResponse } from './types'

export type EstadoCatalogo = 'ACTIVO' | 'INACTIVO'

export interface Materia {
  id: number
  unidad_educativa: number
  unidad_nombre: string
  nombre: string
  estado: EstadoCatalogo
  created_at: string | null
  updated_at: string | null
  eliminado_at: string | null
}

export interface MateriaCurso {
  id: number
  curso: number
  curso_nombre: string
  materia: number
  materia_nombre: string
  profesor?: number | null
  unidad_educativa?: number
  estado?: EstadoCatalogo
}

export interface CursoCatalogo { id: number; nombre: string }
export type ColeccionMateria<T> = PaginatedResponse<T> | T[]

/** El backend puede devolver paginación DRF o, en instalaciones heredadas, un arreglo. */
export const normalizarColeccion = <T,>(data: ColeccionMateria<T>) => Array.isArray(data)
  ? { count: data.length, next: null, previous: null, results: data }
  : { count: data.count ?? data.results?.length ?? 0, next: data.next ?? null, previous: data.previous ?? null, results: data.results ?? [] }
export interface FiltrosMateria {
  unidad_educativa?: number
  estado?: EstadoCatalogo
  nombre?: string
  page?: number
  page_size?: number
}
export interface FiltrosMateriaCurso {
  unidad_educativa?: number
  curso?: number
  materia?: number
  estado?: EstadoCatalogo
  page?: number
  page_size?: number
}

const params = <T extends object>(data: T) => Object.fromEntries(
  Object.entries(data).filter(([, value]) => value !== undefined && value !== null && value !== ''),
)

export const listarMaterias = (filtros: FiltrosMateria, signal?: AbortSignal) =>
  axiosInstance.get<ColeccionMateria<Materia>>('/academico/materias/', { params: params(filtros), signal })
export const crearMateria = (datos: Pick<Materia, 'unidad_educativa' | 'nombre'>) =>
  axiosInstance.post<Materia>('/academico/materias/', datos)
export const actualizarMateria = (id: number, datos: Partial<Pick<Materia, 'unidad_educativa' | 'nombre'>>) =>
  axiosInstance.patch<Materia>(`/academico/materias/${id}/`, datos)
export const desactivarMateria = (id: number) => axiosInstance.post<Materia>(`/academico/materias/${id}/desactivar/`)

export const listarMateriasCurso = (filtros: FiltrosMateriaCurso, signal?: AbortSignal) =>
  axiosInstance.get<ColeccionMateria<MateriaCurso>>('/academico/materias-curso/', { params: params(filtros), signal })
export const vincularMateriaCurso = (datos: { curso: number; materia: number }) =>
  axiosInstance.post<MateriaCurso>('/academico/materias-curso/', datos)
export const actualizarMateriaCurso = (id: number, datos: Partial<{ curso: number; materia: number }>) =>
  axiosInstance.patch<MateriaCurso>(`/academico/materias-curso/${id}/`, datos)
export const desactivarMateriaCurso = (id: number) =>
  axiosInstance.post<MateriaCurso>(`/academico/materias-curso/${id}/desactivar/`)

import axiosInstance from './axiosInstance'
import type { PaginatedResponse } from './types'
import { cargarCatalogoPaginado } from './catalogosPaginados'

export type TipoAsignacion = 'MATERIA' | 'TUTOR_CURSO'

export interface AsignacionDocente {
  id: number
  tipo: TipoAsignacion
  calendario_academico: number | null
  gestion_anio: number | null
  curso: number
  curso_nombre: string
  materia_curso: number | null
  materia_nombre: string | null
  profesor: number
  profesor_nombre: string
  unidad_educativa: number
  unidad_nombre: string
  nivel_educativo: string
  fecha_inicio: string
  fecha_fin: string | null
  horas_semanales: number | null
  estado: 'ACTIVO' | 'INACTIVO'
  created_at: string
  updated_at: string
  eliminado_at: string | null
}

export interface AsignacionPayload {
  calendario_academico: number
  tipo: TipoAsignacion
  curso: number
  profesor: number
  materia_curso: number | null
  fecha_inicio: string
  fecha_fin: string | null
  horas_semanales: number | null
}

export interface FiltrosAsignacion {
  profesor?: number | string
  curso?: number | string
  materia_curso?: number | string
  materia?: number | string
  calendario_academico?: number | string
  gestion?: number | string
  unidad_educativa?: number | string
  tipo?: string
  estado?: string
  page?: number
  vigente?: string
  page_size?: number
}

export interface Calendario { id: number; unidad_educativa: number; unidad_nombre: string; año: number; activo: boolean }
export interface Curso { id: number; nombre: string }
export interface Profesor { id: number; usuario?: { nombre?: string; apellido?: string }; unidad_nombre?: string; estado: boolean }
export interface MateriaCurso { id: number; curso: number; curso_nombre: string; materia: number; materia_nombre: string }

const parametros = (filtros: FiltrosAsignacion) => Object.fromEntries(
  Object.entries(filtros).filter(([, valor]) => valor !== undefined && valor !== null && valor !== ''),
)
export const listarAsignaciones = (params: FiltrosAsignacion, signal?: AbortSignal) =>
  axiosInstance.get<PaginatedResponse<AsignacionDocente>>('/academico/asignaciones-docentes/', { params: parametros(params), signal })
export const crearAsignacion = (payload: AsignacionPayload) =>
  axiosInstance.post<AsignacionDocente>('/academico/asignaciones-docentes/', payload)
export const editarAsignacion = (id: number, payload: Partial<AsignacionPayload>) =>
  axiosInstance.patch<AsignacionDocente>(`/academico/asignaciones-docentes/${id}/`, payload)
export const desactivarAsignacion = (id: number) =>
  axiosInstance.post<AsignacionDocente>(`/academico/asignaciones-docentes/${id}/desactivar/`)

export const listarCalendarios = (unidadEducativa?: number, signal?: AbortSignal) =>
  cargarCatalogoPaginado<Calendario>('/calendario/calendarios/', { unidad_educativa: unidadEducativa }, signal)
export const listarCursos = (unidadEducativa?: number, signal?: AbortSignal) =>
  cargarCatalogoPaginado<Curso>('/academico/cursos/', { unidad_educativa: unidadEducativa }, signal)
export const listarProfesores = (unidad?: number, signal?: AbortSignal) =>
  cargarCatalogoPaginado<Profesor>('/personal/profesores/', { unidad }, signal)
export const listarMateriasCurso = (curso: number, signal?: AbortSignal) =>
  cargarCatalogoPaginado<MateriaCurso>('/academico/materias-curso/', { curso }, signal)


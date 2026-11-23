import axiosInstance from './axiosInstance'
import { normalizeCollection, type PaginatedResponse } from './types'

export interface Periodo { id: number; nombre: string; calendario: number; tipo_division: string; estado: string }

export interface ActividadEvaluacion {
  id: number
  asignacion_docente: number
  curso_nombre: string
  materia_nombre: string
  periodo: number
  periodo_nombre: string
  dimension: number
  dimension_codigo: string
  dimension_nombre: string
  nombre: string
  descripcion: string | null
  fecha: string
  puntaje_maximo: string
  estado: string
}

export interface ActividadPayload {
  asignacion_docente: number
  periodo: number
  dimension: number
  nombre: string
  descripcion?: string | null
  fecha: string
  puntaje_maximo: string
}

export interface FilaGrilla {
  estudiante: number
  estudiante_nombre: string
  historial_inscripcion: number | null
  notas: Record<number, string | null>
  resultado_trimestral: string | null
  condicion: string | null
}

export interface Grilla { actividades: ActividadEvaluacion[]; estudiantes: FilaGrilla[] }

export interface DimensionEvaluacion { id: number; codigo: string; nombre: string; ponderacion: string; orden: number }

interface ConfiguracionEvaluacionConDimensiones { dimensiones: DimensionEvaluacion[] }

export const listarActividades = (params: { asignacion_docente?: number; periodo?: number }) =>
  axiosInstance.get<PaginatedResponse<ActividadEvaluacion> | ActividadEvaluacion[]>(
    '/academico/actividades-evaluacion/', { params },
  )

export const crearActividad = (payload: ActividadPayload) =>
  axiosInstance.post<ActividadEvaluacion>('/academico/actividades-evaluacion/', payload)

export const obtenerGrilla = (asignacionDocente: number, periodo: number) =>
  axiosInstance.get<Grilla>('/academico/actividades-evaluacion/grilla/', {
    params: { asignacion_docente: asignacionDocente, periodo },
  })

export const guardarCalificacionesActividad = (
  actividadId: number, calificaciones: Array<{ historial_inscripcion: number; valor: string }>,
) =>
  axiosInstance.put(`/academico/actividades-evaluacion/${actividadId}/calificaciones/`, { calificaciones })

const obtenerCatalogo = async <T>(url: string, params?: Record<string, unknown>) =>
  normalizeCollection((await axiosInstance.get<T[] | PaginatedResponse<T>>(url, { params })).data)

export const listarPeriodos = (calendarioId?: number) =>
  obtenerCatalogo<Periodo>('/calendario/periodos/', calendarioId ? { calendario: calendarioId } : undefined)

export const listarDimensiones = async (calendarioId: number, nivel: string) => {
  const configuraciones = await obtenerCatalogo<ConfiguracionEvaluacionConDimensiones>(
    '/academico/configuraciones-evaluacion/', { calendario_academico: calendarioId, nivel },
  )
  return configuraciones[0]?.dimensiones ?? []
}

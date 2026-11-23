import axios from './axiosInstance'
import type { DatosEstudiante, EstudianteApi, ResultadoInscripcion } from '../pages/inscripcion/types'

export interface InscripcionData {
  estudiante_id?: number
  usuario_id?: number
  nuevo_estudiante?: DatosEstudiante
  curso_id: number
  unidad_id: number
  rude: string
  observaciones?: string
}

interface RespuestaPaginada<T> {
  results: T[]
}

const extraerLista = <T>(data: T[] | RespuestaPaginada<T>): T[] =>
  Array.isArray(data) ? data : data.results ?? []

const mensajeError = (error: unknown, mensajePredeterminado: string) => {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: unknown } }).response
    const data = response?.data
    if (typeof data === 'string') return data
    if (typeof data === 'object' && data !== null && 'detail' in data) {
      return String((data as { detail: unknown }).detail)
    }
    if (data) return JSON.stringify(data)
  }
  return mensajePredeterminado
}

export const obtenerEstudiantes = async (): Promise<EstudianteApi[]> => {
  const response = await axios.get<EstudianteApi[] | RespuestaPaginada<EstudianteApi>>(
    '/estudiantes/estudiantes/listar/',
  )
  return extraerLista(response.data)
}

export const inscribirEstudiante = async (
  data: InscripcionData,
): Promise<ResultadoInscripcion> => {
  try {
    const response = await axios.post<ResultadoInscripcion>(
      '/estudiantes/estudiantes/inscribir/',
      data,
    )
    return response.data
  } catch (error: unknown) {
    throw new Error(mensajeError(error, 'Error al inscribir al estudiante'), { cause: error })
  }
}

export const cambiarInscripcion = async (
  usuarioId: number,
  data: InscripcionData,
): Promise<ResultadoInscripcion> => {
  try {
    const response = await axios.post<ResultadoInscripcion>(
      `/estudiantes/estudiantes/${usuarioId}/cambiar-inscripcion/`,
      data,
    )
    return response.data
  } catch (error: unknown) {
    throw new Error(mensajeError(error, 'Error al cambiar la inscripción'), { cause: error })
  }
}

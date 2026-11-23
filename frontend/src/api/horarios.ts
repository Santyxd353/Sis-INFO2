import api from './axiosInstance'

export interface HorarioPayload {
  asignacion_docente: number
  aula: number
  dia: number
  hora_inicio: string
  hora_fin: string
  fecha_inicio: string
  fecha_fin: string
}
export interface Horario extends Omit<HorarioPayload, 'fecha_fin'> {
  fecha_fin: string | null
  id: number
  profesor: number
  curso: number
  unidad_educativa: number
  colegio: number
  profesor_nombre: string
  curso_nombre: string
  materia_nombre: string
  aula_nombre: string
  gestion: number
  estado: string
}
export interface OpcionHorario { id: number; nombre: string }
export interface AulaHorario extends OpcionHorario { colegio: number; unidad_educativa: number }
export interface AsignacionHorario extends OpcionHorario {
  profesor: number
  curso: number
  unidad_educativa: number
  colegio: number
  gestion: number
  fecha_inicio: string
  fecha_fin: string
}
export const guardarHorario = (payload: HorarioPayload, id?: number) => id
  ? api.patch<Horario>(`/academico/horarios/${id}/`, payload)
  : api.post<Horario>('/academico/horarios/', payload)
export const eliminarHorario = (id: number) => api.delete(`/academico/horarios/${id}/`)

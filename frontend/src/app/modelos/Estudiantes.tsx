import type { Usuario } from './Usuarios'
import type { UnidadEducativa } from './Institucion'
import type { Curso } from './Academico'

export interface Estudiante {
  id: number
  usuario: Usuario
  rude: string
  estado: boolean
  curso?: Curso
  unidad: UnidadEducativa
}

export interface Tutor {
  id?: number
  usuario: Usuario
  parentesco: 'PAD' | 'MAD' | 'TUT' | 'HER' | 'OTR'
  parentesco_display: string
}

export interface TutorEstudiante {
  id: number
  tutor: Tutor
  estudiante: Estudiante
  fecha_asignacion: string
  es_principal: boolean
}

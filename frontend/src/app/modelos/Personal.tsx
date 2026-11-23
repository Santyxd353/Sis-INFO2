import type { Materia, Grado } from './Academico'
import type { Usuario } from './Usuarios'
import type { UnidadEducativa } from './Institucion'

export interface Especialidad {
  id: number
  nombre: string
  materia: Materia
  grado?: Grado
}

export interface Profesor {
  usuario: Usuario
  estado: boolean
  unidad: UnidadEducativa
}

export interface ProfesorEspecialidad {
  id: number
  profesor: Profesor
  especialidad: Especialidad
  fecha_asignacion: string
}

import type { Periodo } from './Calendario'

export interface CargaHoraria {
  id: number
  profesor: Profesor
  especialidad: Especialidad
  profesor_especialidad?: ProfesorEspecialidad
  horas: number
  periodo: Periodo
}

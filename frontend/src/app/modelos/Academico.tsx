import type { UnidadEducativa } from './Institucion'

export interface Clase {
  id: number
  cursoId: number
  aulaId: number
}

export type NivelEducativo = 'INI' | 'PRI' | 'SEC'

export interface Grado {
  id: number
  nivel_educativo: string
  numero: number
  unidad_educativa: UnidadEducativa
  nombre: string
}

export interface Paralelo {
  id: number
  grado: Grado
  gradoId?: number
  letra: string
}

import type { Profesor } from './Personal'

export interface Curso {
  id: number
  paraleloId: number
  nombre: string
  paralelo: Paralelo
  tutor: Profesor
}

export interface Materia {
  id: number
  nombre: string
}

export interface MateriaCurso {
  id: number
  nombre_completo: string
  curso_id: number
  curso: Curso
  materia: Materia
  materia_id: number
  profesor: Profesor
}

import type { Aula } from './Institucion'

export interface Clase {
  id: number
  materia_curso: MateriaCurso
  aula: Aula
  materia_curso_id?: number
  aula_id?: number
}

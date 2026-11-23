export interface DatosEstudiante {
  nombre: string
  apellido: string
  ci: string
  email: string
  sexo: string
  username?: string
  password?: string
}

export interface EstudianteSeleccionado {
  usuario_id?: number
  estudiante_id?: number
  es_nuevo: boolean
  datos: DatosEstudiante
}

export interface CursoSeleccionado {
  curso_id: number
  curso_nombre: string
  grado: string
  paralelo: string
  unidad_id: number
  unidad_nombre: string
}

export interface UsuarioResumen extends DatosEstudiante {
  id: number
}

export interface EstudianteApi {
  id: number
  usuario: UsuarioResumen
  rude: string
  estado: boolean
  curso?: {
    paralelo_id: number
    nombre: string
  } | null
  unidad?: {
    id: number
    nombre: string
  } | null
}

export type ResultadoInscripcion = EstudianteApi

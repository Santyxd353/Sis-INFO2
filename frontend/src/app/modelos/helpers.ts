import { Usuario } from './Usuarios'
import type { Rol } from './Usuarios'
import type { Estudiante, TutorEstudiante } from './Estudiantes'
import type { Turno } from './Calendario'

export function emptyUsuario(): Usuario {
  return new Usuario({
    id: 0,
    ci: '',
    nombre: '',
    apellido: '',
    sexo: 'M',
    email: '',
    fecha_nacimiento: null,
    username: '',
    estado: true,
    rol: { id: 0, nombre: '', descripcion: '' } as Rol,
    telefono: null,
    password: null,
    is_staff: false,
    is_active: true,
    date_joined: new Date().toISOString(),
    puesto: undefined,
  })
}

export function emptyEstudiante(): Estudiante {
  return {
    id: 0,
    usuario: emptyUsuario(),
    rude: '',
    estado: true,
    unidad: {
      id: 0,
      nombre: '',
      direccion: '',
      telefono: '',
      nivel: '',
      codigo_sie: '',
      turno: 'MAÑANA' as Turno,
      colegio: { id: 0, nombre: '' },
    },
  }
}

export function emptyTutorEstudiante(): TutorEstudiante {
  return {
    id: 0,
    tutor: { usuario: emptyUsuario(), parentesco: 'OTR', parentesco_display: 'Otro' },
    estudiante: emptyEstudiante(),
    fecha_asignacion: '',
    es_principal: false,
  }
}

import type { Colegio, UnidadEducativa } from './Institucion'

export type InstitutionalScopeType = 'GLOBAL' | 'COLEGIO' | 'UNIDAD' | 'PERSONAL'

export interface InstitutionalScope {
  tipo: InstitutionalScopeType
  colegio_id: number | null
  colegio_nombre: string | null
  unidad_id: number | null
  unidad_nombre: string | null
}

export interface EffectivePermission {
  modelo: string
  accion: string
}

export interface PermisoUi {
  componente: string
  visible: boolean
  editable: boolean
}

type UsuarioData = {
  id: number
  ci: string
  foto?: string | null
  nombre: string
  apellido: string
  sexo: string
  email: string
  fecha_nacimiento?: string | null
  username: string
  estado: boolean
  rol: Rol
  telefono?: string | null
  password?: string | null
  is_staff: boolean
  is_active: boolean
  date_joined: string
  puesto?: Puesto
  colegio?: Colegio | null
  unidad?: UnidadEducativa | null
  debe_cambiar_password?: boolean
  perfil?: Usuario['perfil']
  alcance?: InstitutionalScope | null
  permisos_efectivos?: EffectivePermission[]
  permisos_ui?: PermisoUi[]
}

export class Rol {
  id: number
  nombre: string
  descripcion?: string | null

  constructor(data: { id: number; nombre: string; descripcion?: string | null }) {
    this.id = data.id
    this.nombre = data.nombre
    this.descripcion = data.descripcion ?? null
  }
}

export class Usuario {
  id: number
  ci: string
  foto?: string | null
  nombre: string
  apellido: string
  sexo: string
  email: string
  fecha_nacimiento?: string | null
  username: string
  estado: boolean
  rol: Rol
  telefono?: string | null
  password?: string | null
  is_staff: boolean
  is_active: boolean
  date_joined: string
  puesto?: Puesto
  colegio?: Colegio | null
  unidad?: UnidadEducativa | null
  debe_cambiar_password: boolean
  perfil?: {
    tipo: string
    puesto?: Puesto | null
    cursos?: Array<{ id: number; nombre: string }>
    curso?: { id: number; nombre: string } | null
    rude?: string
    parentesco?: string
  } | null
  alcance: InstitutionalScope | null
  permisos_efectivos: EffectivePermission[]
  permisos_ui: PermisoUi[]

  constructor(data: UsuarioData) {
    this.id = data.id
    this.ci = data.ci
    this.foto = data.foto ?? null
    this.nombre = data.nombre
    this.apellido = data.apellido
    this.sexo = data.sexo
    this.email = data.email
    this.fecha_nacimiento = data.fecha_nacimiento ?? null
    this.username = data.username
    this.estado = data.estado
    this.rol = data.rol
    this.telefono = data.telefono ?? null
    this.password = data.password ?? null
    this.is_staff = data.is_staff
    this.is_active = data.is_active
    this.date_joined = data.date_joined
    this.puesto = data.puesto
    this.colegio = data.colegio ?? null
    this.unidad = data.unidad ?? null
    this.debe_cambiar_password = data.debe_cambiar_password ?? false
    this.perfil = data.perfil ?? null
    this.alcance = data.alcance ?? null
    this.permisos_efectivos = data.permisos_efectivos ?? []
    this.permisos_ui = data.permisos_ui ?? []
  }
}

export const canEffectivePermission = (
  user: Pick<Usuario, 'permisos_efectivos'> | null | undefined,
  modelo: string,
  accion: string,
) => Boolean(user?.permisos_efectivos?.some(
  (permiso) => permiso.modelo === modelo && permiso.accion === accion,
))

export class SuperAdmin {
  usuarioId: number
  usuario: Usuario
  constructor(data: { usuarioId: number; usuario: Usuario }) {
    this.usuarioId = data.usuarioId
    this.usuario = data.usuario
  }
}

export type Puesto = {
  id: number
  nombre: string
  descripcion?: string | null
}

export type Accion = {
  id: number
  nombre: string
}

export type PermisoRol = {
  id: number
  rol: Rol
  rol_nombre: string
  modelo: ModeloPermitido
  modelo_nombre: string
  accion: Accion
  accion_nombre: string
}

export type ModeloPermitido = {
  id: number
  nombre: string
}

export type PermisoPuesto = {
  id: number
  puesto: Puesto
  modelo: ModeloPermitido
  accion: Accion
}

export interface Admin {
  usuarioId: number
  usuario: Usuario
  puesto?: Puesto
  unidad: UnidadEducativa
  estado: boolean
}

export type AccionBitacora = 'crear' | 'editar' | 'eliminar' | 'listar' | 'otro'

export interface Bitacora {
  id: number
  usuario: Usuario
  hora_entrada: string
  hora_salida?: string | null
  ip?: string | null
  tabla_afectada?: string | null
  accion: AccionBitacora
  descripcion?: string | null
  fecha: string
}

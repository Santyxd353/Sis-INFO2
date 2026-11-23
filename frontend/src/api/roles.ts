import axiosInstance from './axiosInstance'
import { normalizeCollection } from './types'

export interface PermisoPar {
  modelo: string
  accion: string
}

export interface ComponentePermiso {
  id?: number
  componente: string
  visible: boolean
  editable: boolean
}

export interface Rol {
  id: number
  nombre: string
  descripcion: string | null
  colegio_id: number | null
  unidad_id?: number | null
  puesto_id?: number | null
  puesto?: { id: number; nombre: string } | null
  activo: boolean
  categoria: 'BASE' | 'FUNCIONAL'
  alcance: 'SISTEMA' | 'COLEGIO' | 'UNIDAD'
  asignable?: boolean
  permisos: PermisoPar[]
  componentes: ComponentePermiso[]
}

export interface RolPayload {
  nombre: string
  descripcion?: string
  colegio_id?: number | null
  unidad_id?: number | null
  puesto_id?: number | null
  activo?: boolean
}

export interface RespuestaPermisos {
  rol_id: number
  permisos: PermisoPar[]
  metadatos?: Array<PermisoPar & { directo: boolean; heredado: boolean; disponible: boolean; bloqueado: boolean; motivo_bloqueo?: string | null }>
}

export interface ConfiguracionInstitucional {
  rol_id: number | null
  rol: Rol | null
  perfil_objetivo: { id: number; nombre: string }
  alcance: 'COLEGIO' | 'UNIDAD'
  colegio_id: number
  unidad: { id: number; nombre: string } | null
  permisos: PermisoPar[]
  permisos_disponibles: PermisoPar[]
  permisos_heredados: PermisoPar[]
  permisos_bloqueados: Array<PermisoPar & { motivo_bloqueo?: string | null }>
  metadatos: Array<PermisoPar & { directo: boolean; heredado: boolean; disponible: boolean; bloqueado: boolean; motivo_bloqueo?: string | null }>
  puede_editar: boolean
}

export interface RespuestaComponentes {
  rol_id: number
  componentes: ComponentePermiso[]
}

export interface RolUsuario {
  id: number
  nombre: string
}

export interface RespuestaRolesUsuario {
  usuario_id: number
  roles: RolUsuario[]
}

export interface CatalogoItem {
  id: number
  nombre: string
}

export const listarRolesGestion = () =>
  axiosInstance.get<Rol[]>('/usuarios/roles/', { params: { gestion: '1' } })

export const listarRolesAsignables = () =>
  axiosInstance.get<Rol[]>('/usuarios/roles/', { params: { asignables: '1' } })

export const obtenerRol = (id: number) =>
  axiosInstance.get<Rol>(`/usuarios/roles/${id}/`)

export const crearRol = (payload: RolPayload) =>
  axiosInstance.post<Rol>('/usuarios/roles/', payload)

export const editarRol = (id: number, payload: Partial<RolPayload>) =>
  axiosInstance.patch<Rol>(`/usuarios/roles/${id}/`, payload)

export const eliminarRol = (id: number) =>
  axiosInstance.delete(`/usuarios/roles/${id}/`)

export const obtenerPermisosRol = (id: number) =>
  axiosInstance.get<RespuestaPermisos>(`/usuarios/roles/${id}/permisos/`)

export const guardarPermisosRol = (id: number, permisos: PermisoPar[]) =>
  axiosInstance.put<RespuestaPermisos>(`/usuarios/roles/${id}/permisos/`, { permisos })

export const obtenerComponentesRol = (id: number) =>
  axiosInstance.get<RespuestaComponentes>(`/usuarios/roles/${id}/componentes/`)

export const guardarComponentesRol = (id: number, componentes: ComponentePermiso[]) =>
  axiosInstance.put<RespuestaComponentes>(
    `/usuarios/roles/${id}/componentes/`,
    { componentes: componentes.map(({ componente, visible, editable }) => ({ componente, visible, editable })) },
  )

export const obtenerConfiguracionInstitucional = (params: { puesto_id: number; unidad_id?: number | null }) =>
  axiosInstance.get<ConfiguracionInstitucional>('/usuarios/roles/configuracion-institucional/', { params })

export const guardarConfiguracionInstitucional = (payload: { puesto_id: number; unidad_id?: number | null; permisos: PermisoPar[] }) =>
  axiosInstance.put<ConfiguracionInstitucional>('/usuarios/roles/configuracion-institucional/', payload)

export const obtenerRolesUsuario = (usuarioId: number) =>
  axiosInstance.get<RespuestaRolesUsuario>(`/usuarios/usuarios/${usuarioId}/roles/`)

export const asignarRolesUsuario = (usuarioId: number, rolIds: number[]) =>
  axiosInstance.put<RespuestaRolesUsuario>(`/usuarios/usuarios/${usuarioId}/roles/`, { rol_ids: rolIds })

export const listarAcciones = () =>
  axiosInstance.get<CatalogoItem[]>('/usuarios/acciones/')

export const listarModelosPermitidos = () =>
  axiosInstance.get<CatalogoItem[]>('/usuarios/modelos-permitidos/')

export const normalizarRoles = (data: Rol[] | { count: number; results: Rol[] }): Rol[] =>
  normalizeCollection<Rol>(data)

export const normalizarCatalogo = (
  data: CatalogoItem[] | { count: number; results: CatalogoItem[] },
): CatalogoItem[] => normalizeCollection<CatalogoItem>(data)

import type { LucideIcon } from 'lucide-react'
import type { ModuloPanel } from '../../pages/dashboard/modules'

export type ModuleStatus = 'IMPLEMENTED' | 'DISABLED' | 'FUTURE'
export type NavigationScope = 'GLOBAL' | 'COLEGIO' | 'UNIDAD' | 'PERSONAL'
export type VisualProfile = 'SUPERADMIN' | 'ADMINISTRADOR_INSTITUCIONAL' | 'DIRECTOR' | 'SECRETARIA' | 'TESORERIA' | 'PROFESOR' | 'REGENTE' | 'TUTOR' | 'ESTUDIANTE' | 'UNKNOWN'

export interface NavigationModule extends ModuloPanel {
  key: string
  grupo: string
  permiso?: { modelo: string; accion: 'listar' | 'crear' | 'editar' | 'eliminar' | 'desactivar' }
  perfiles: VisualProfile[]
  alcance: NavigationScope
  alcancesCompatibles?: NavigationScope[]
  estadoFuncional: ModuleStatus
  sprint: 1 | 2 | 3
  orden: number
  icono: LucideIcon
}

export interface NavigationGroup {
  key: string
  nombre: string
  orden: number
  modulos: NavigationModule[]
}

export interface InstitutionalContext {
  colegioId: number
  colegioNombre: string
  unidadId?: number
  unidadNombre?: string
}


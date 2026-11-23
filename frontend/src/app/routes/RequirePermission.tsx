import type { ReactElement } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { resolveVisualProfile } from '../navigation/navigationConfig'
import type { NavigationScope, VisualProfile } from '../navigation/types'

export default function RequirePermission({ modelos, accion = 'listar', allowPersonalProfessor = false, profiles, scopes, children }: {
  modelos: string[]
  accion?: 'listar' | 'crear' | 'editar' | 'eliminar' | 'desactivar'
  allowPersonalProfessor?: boolean
  profiles?: VisualProfile[]
  scopes?: NavigationScope[]
  children: ReactElement
}) {
  const { can, user, isProfesor, permisosCargando } = useAuth()
  if (permisosCargando) {
    return <div className="p-8 text-sm text-slate-500">Cargando permisos...</div>
  }
  if (profiles && !profiles.includes(resolveVisualProfile(user))) return <Navigate to="/no-permission" replace />
  if (scopes && (!user?.alcance?.tipo || !scopes.includes(user.alcance.tipo))) return <Navigate to="/no-permission" replace />
  const politicaPersonal = allowPersonalProfessor
    && isProfesor() && user?.alcance?.tipo === 'PERSONAL' && accion === 'listar'
  if (politicaPersonal || modelos.some((modelo) => can(modelo, accion))) return children
  return <Navigate to="/no-permission" replace />
}

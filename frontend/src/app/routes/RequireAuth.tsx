import { Navigate, useLocation } from 'react-router-dom'
import type { ReactElement } from 'react'
import { useAuth } from '../contexts/AuthContext'

interface RequireAuthProps {
  children: ReactElement
  allowedRoles?: string[]
}

export default function RequireAuth({ children, allowedRoles }: RequireAuthProps): ReactElement {
  const { user, loading, hasRole, isSuperAdmin } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 text-sm font-semibold text-brand-700">
        Cargando panel...
      </div>
    )
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  if (isSuperAdmin()) return children
  if (allowedRoles && allowedRoles.length > 0 && !hasRole(allowedRoles)) {
    return <Navigate to="/dashboard/no-permission" replace />
  }
  return children
}

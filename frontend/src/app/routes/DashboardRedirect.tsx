import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { dashboardPath } from './dashboardPath'

export default function DashboardRedirect() {
  const { user, loading } = useAuth()
  if (loading) return <div className="grid min-h-screen place-items-center text-sm font-semibold text-brand-700">Restaurando sesión...</div>
  return <Navigate to={dashboardPath(user)} replace />
}

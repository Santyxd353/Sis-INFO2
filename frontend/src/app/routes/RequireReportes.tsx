import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { permisosReportes } from '../navigation/reportesPermisos'
import ReportesPage from '../../pages/evaluacion/ReportesPage'

export default function RequireReportes() {
  const { user, permisosCargando } = useAuth()
  if (permisosCargando) return <div className="p-8">Cargando permisos...</div>
  const permisos = permisosReportes(user)
  return permisos.operativo || permisos.qbe || permisos.analitico ? <ReportesPage /> : <Navigate to="/no-permission" replace />
}

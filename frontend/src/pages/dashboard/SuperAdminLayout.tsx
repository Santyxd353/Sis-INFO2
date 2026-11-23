import RoleLayout from './RoleLayout'
import { useAuth } from '../../app/contexts/AuthContext'
import { buildNavigation } from '../../app/navigation/navigationConfig'

export default function SuperAdminLayout() {
  const { user, can } = useAuth()
  const modulos = buildNavigation(user, can).flatMap((grupo) => grupo.modulos)
  return <RoleLayout
    basePath="/dashboard/superadmin"
    titulo="Panel Super Administrador"
    subtitulo="Administración global de la plataforma"
    modulos={modulos}
  />
}

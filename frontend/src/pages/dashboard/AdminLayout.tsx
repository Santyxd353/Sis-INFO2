import { useAuth } from '../../app/contexts/AuthContext'
import RoleLayout from './RoleLayout'
import { buildNavigation } from '../../app/navigation/navigationConfig'

export default function AdminLayout() {
  const { user, can } = useAuth()
  const modulos = buildNavigation(user, can).flatMap((grupo) => grupo.modulos)
  return <RoleLayout
    basePath="/dashboard/admin"
    titulo="Panel Administrativo"
    subtitulo="Gestión de la unidad educativa"
    modulos={modulos}
  />
}

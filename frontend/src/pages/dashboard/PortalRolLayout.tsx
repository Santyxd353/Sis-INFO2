import { useAuth } from '../../app/contexts/AuthContext'
import RoleLayout from './RoleLayout'
import { buildNavigation } from '../../app/navigation/navigationConfig'

export default function PortalRolLayout({ basePath, titulo }: { basePath: string; titulo: string }) {
  const { user, can } = useAuth()
  return <RoleLayout
    basePath={basePath}
    titulo={titulo}
    subtitulo={user?.unidad?.nombre ?? 'Portal educativo'}
    modulos={buildNavigation(user, can).flatMap((grupo) => grupo.modulos)}
  />
}

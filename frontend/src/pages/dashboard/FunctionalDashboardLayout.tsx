import { useAuth } from '../../app/contexts/AuthContext'
import RoleLayout from './RoleLayout'
import { buildNavigation } from '../../app/navigation/navigationConfig'
import { resolveVisualProfile } from '../../app/navigation/navigationConfig'
import { dashboardPath } from '../../app/routes/dashboardPath'

export default function FunctionalDashboardLayout() {
  const { can, user } = useAuth()
  const perfil = resolveVisualProfile(user)
  const basePath = dashboardPath(user)
  const titulos = { SUPERADMIN: 'Panel Super Administrador', ADMINISTRADOR_INSTITUCIONAL: 'Panel Administrativo', DIRECTOR: 'Dirección académica', SECRETARIA: 'Secretaría académica', TESORERIA: 'Panel de Tesorería', PROFESOR: 'Panel Docente', REGENTE: 'Panel de Regencia', TUTOR: 'Portal de Tutor', ESTUDIANTE: 'Portal del Estudiante', UNKNOWN: 'Portal educativo' }
  const titulo = titulos[perfil]
  const modulos = buildNavigation(user, can).flatMap((grupo) => grupo.modulos)
  return <RoleLayout basePath={basePath} titulo={titulo} subtitulo={user?.unidad?.nombre ?? 'Gestión académica'} modulos={modulos} />
}

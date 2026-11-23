import type { Usuario } from '../modelos/Usuarios'
import { resolveVisualProfile } from '../navigation/navigationConfig'

export const dashboardPath = (usuario: Pick<Usuario, 'rol' | 'perfil' | 'puesto'> | null | undefined) => {
  const paths = {
    SUPERADMIN: '/dashboard/superadmin',
    DIRECTOR: '/dashboard/director',
    SECRETARIA: '/dashboard/secretaria',
    TESORERIA: '/dashboard/tesoreria',
    ADMINISTRADOR_INSTITUCIONAL: '/dashboard/admin',
    PROFESOR: '/dashboard/profesor',
    REGENTE: '/dashboard/regente',
    TUTOR: '/dashboard/tutor',
    ESTUDIANTE: '/dashboard/estudiante',
    UNKNOWN: '/dashboard/no-permission',
  } as const
  return paths[resolveVisualProfile(usuario)]
}

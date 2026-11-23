import type { Usuario } from '../modelos/Usuarios'
import { MODULE_CATALOG, NAVIGATION_GROUPS } from './moduleCatalog'
import type { NavigationGroup, VisualProfile } from './types'
import { canEffectivePermission } from '../modelos/Usuarios'

const normalizar = (valor?: string | null) => valor?.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[_-]/g,' ') ?? ''

export const resolveVisualProfile = (user: Pick<Usuario,'rol'|'perfil'|'puesto'> | null | undefined): VisualProfile => {
  const rol = normalizar(user?.rol?.nombre)
  const puesto = normalizar(user?.perfil?.puesto?.nombre ?? user?.puesto?.nombre)
  if (['superadmin','super admin'].includes(rol)) return 'SUPERADMIN'
  if (rol === 'director' || puesto === 'director') return 'DIRECTOR'
  if (['secretaria','secretario'].includes(rol) || ['secretaria','secretario'].includes(puesto)) return 'SECRETARIA'
  if (rol === 'admin' && puesto === 'tesoreria') return 'TESORERIA'
  if (rol === 'regente' || puesto === 'regente') return 'REGENTE'
  if (['admin','administrador','administrador institucional'].includes(rol)) return 'ADMINISTRADOR_INSTITUCIONAL'
  if (rol === 'profesor') return 'PROFESOR'
  if (rol === 'tutor') return 'TUTOR'
  if (rol === 'estudiante') return 'ESTUDIANTE'
  return 'UNKNOWN'
}

export const buildNavigation = (user: Usuario | null, can: (modelo:string,accion:string)=>boolean): NavigationGroup[] => {
  const perfil = resolveVisualProfile(user)
  const alcance = user?.alcance?.tipo
  const modulos = MODULE_CATALOG.filter((modulo) => {
    if (perfil !== 'SUPERADMIN' && user?.permisos_ui?.some((p) => p.componente === `modulo:${modulo.key}` && !p.visible)) return false
    if (modulo.key === 'reportes') return ['COLEGIO', 'UNIDAD'].includes(alcance ?? '') && ['DIRECTOR', 'SECRETARIA'].includes(perfil) && ((canEffectivePermission(user, 'reporte-definicion', 'listar') && canEffectivePermission(user, 'reporte-ejecucion', 'ejecutar')) || (canEffectivePermission(user, 'reporte-qbe', 'validar') && canEffectivePermission(user, 'reporte-qbe', 'ejecutar')) || canEffectivePermission(user, 'reporte-analitico', 'listar'))
    if (modulo.estadoFuncional !== 'IMPLEMENTED' || !modulo.perfiles.includes(perfil)) return false
    if (!alcance) return false
    const compatibles = modulo.alcancesCompatibles ?? [modulo.alcance]
    if (alcance !== 'GLOBAL' && !compatibles.includes(alcance)) return false
    if (perfil === 'SUPERADMIN') return alcance === 'GLOBAL'
    if (!modulo.permiso) {
      if (!modulo.recursos) return true
      return modulo.recursos.some((recurso) => {
        const endpoint = recurso.endpoint
        const mapa: Record<string,string> = {'institucion':'unidad-educativa','usuarios':'usuario','calendario':'calendario','academico':'curso','personal':'profesor','estudiantes':'estudiante'}
        return can(mapa[endpoint.split('/').filter(Boolean)[0]] ?? '', 'listar')
      })
    }
    const modulosPersonalesDocente = ['asignaciones', 'evaluacion', 'correcciones']
    return (
      perfil === 'PROFESOR' && alcance === 'PERSONAL' && modulosPersonalesDocente.includes(modulo.key)
    ) || can(modulo.permiso.modelo, modulo.permiso.accion)
  }).sort((a,b)=>a.orden-b.orden)
  return NAVIGATION_GROUPS.map((grupo) => ({...grupo,modulos:modulos.filter((m)=>m.grupo===grupo.key)})).filter((grupo)=>grupo.modulos.length>0)
}


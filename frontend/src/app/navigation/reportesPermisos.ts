import type { Usuario } from '../modelos/Usuarios'
import { canEffectivePermission } from '../modelos/Usuarios'
import { resolveVisualProfile } from './navigationConfig'

export function permisosReportes(user: Usuario | null) {
  const perfil = resolveVisualProfile(user)
  const contexto = user?.alcance?.tipo === 'COLEGIO' || user?.alcance?.tipo === 'UNIDAD'
  const autorizado = contexto && (perfil === 'DIRECTOR' || perfil === 'SECRETARIA')
  return {
    operativo: autorizado && canEffectivePermission(user, 'reporte-definicion', 'listar') && canEffectivePermission(user, 'reporte-ejecucion', 'ejecutar'),
    qbe: autorizado && canEffectivePermission(user, 'reporte-qbe', 'validar') && canEffectivePermission(user, 'reporte-qbe', 'ejecutar'),
    analitico: autorizado && canEffectivePermission(user, 'reporte-analitico', 'listar'),
  }
}

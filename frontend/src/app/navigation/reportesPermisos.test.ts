import { describe, expect, it } from 'vitest'
import type { Usuario } from '../modelos/Usuarios'
import { permisosReportes } from './reportesPermisos'
import { buildNavigation } from './navigationConfig'

const operativo = [{ modelo: 'reporte-definicion', accion: 'listar' }, { modelo: 'reporte-ejecucion', accion: 'ejecutar' }]
const qbe = [{ modelo: 'reporte-qbe', accion: 'validar' }, { modelo: 'reporte-qbe', accion: 'ejecutar' }]
const perfil = (rol: string, permisos = [...operativo, ...qbe], tipo = 'COLEGIO') => ({ rol: { nombre: rol }, alcance: { tipo, colegio_id: 1, unidad_id: tipo === 'UNIDAD' ? 1 : null }, permisos_efectivos: permisos }) as Usuario

describe('permisos de reportes', () => {
  it('permite los dos paneles a Dirección con permisos', () => expect(permisosReportes(perfil('Director'))).toEqual({ operativo: true, qbe: true, analitico: false }))
  it('permite solamente el panel autorizado', () => {
    expect(permisosReportes(perfil('Director', operativo))).toEqual({ operativo: true, qbe: false, analitico: false })
    expect(permisosReportes(perfil('Director', qbe))).toEqual({ operativo: false, qbe: true, analitico: false })
    expect(permisosReportes(perfil('Secretaria', operativo, 'UNIDAD'))).toEqual({ operativo: true, qbe: false, analitico: false })
  })
  it('niega perfiles ajenos y superadministrador sin contexto', () => {
    for (const nombre of ['Profesor', 'Tutor', 'Estudiante']) expect(permisosReportes(perfil(nombre))).toEqual({ operativo: false, qbe: false, analitico: false })
    expect(permisosReportes(perfil('SuperAdmin', [], 'GLOBAL'))).toEqual({ operativo: false, qbe: false, analitico: false })
  })
  it('incluye el menú para Dirección con solo QBE', () => {
    const grupos = buildNavigation(perfil('Director', qbe), () => false)
    expect(JSON.stringify(grupos)).toContain('/dashboard/reportes')
  })
})

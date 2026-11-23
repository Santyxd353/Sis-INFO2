import { describe, expect, it } from 'vitest'
import type { Usuario } from '../modelos/Usuarios'
import { MODULE_CATALOG } from './moduleCatalog'
import { buildNavigation, resolveVisualProfile } from './navigationConfig'

const usuario = (rol: string, puesto?: string) => ({
  rol: { id: 1, nombre: rol },
  perfil: puesto ? { tipo: 'Admin', puesto: { id: 1, nombre: puesto } } : null,
  alcance: rol.toLowerCase() === 'superadmin'
    ? { tipo: 'GLOBAL', colegio_id: null, colegio_nombre: null, unidad_id: null, unidad_nombre: null }
    : rol.toLowerCase() === 'profesor'
      ? { tipo: 'PERSONAL', colegio_id: 1, colegio_nombre: 'Colegio', unidad_id: 2, unidad_nombre: 'Unidad' }
      : puesto?.toLowerCase().includes('director')
        ? { tipo: 'COLEGIO', colegio_id: 1, colegio_nombre: 'Colegio', unidad_id: null, unidad_nombre: null }
        : { tipo: 'UNIDAD', colegio_id: 1, colegio_nombre: 'Colegio', unidad_id: 2, unidad_nombre: 'Unidad' },
  permisos_efectivos: [],
} as unknown as Usuario)

const keys = (rol: string, puesto?: string, permitir = () => true) =>
  buildNavigation(usuario(rol, puesto), permitir).flatMap((grupo) => grupo.modulos.map((modulo) => modulo.key))

describe('configuración central de navegación', () => {
  it('respeta la ocultación explícita de una sección del menú', () => {
    const director = usuario('Admin', 'Director')
    director.permisos_ui = [{ componente: 'modulo:roles', visible: false, editable: false }]
    const modulos = buildNavigation(director, () => true).flatMap((grupo) => grupo.modulos.map((modulo) => modulo.key))
    expect(modulos).not.toContain('roles')
    expect(modulos).toContain('suscripciones')
  })
  it('normaliza SuperAdmin', () => expect(resolveVisualProfile(usuario('SuperAdmin'))).toBe('SUPERADMIN'))
  it('normaliza administrador institucional', () => expect(resolveVisualProfile(usuario('Admin'))).toBe('ADMINISTRADOR_INSTITUCIONAL'))
  it('prioriza el puesto Director', () => expect(resolveVisualProfile(usuario('Admin', 'Director'))).toBe('DIRECTOR'))
  it('normaliza Secretaría sin depender de acentos', () => expect(resolveVisualProfile(usuario('Admin', 'Secretaría'))).toBe('SECRETARIA'))
  it('resuelve Tesorería como perfil institucional sin permisos implícitos', () => {
    const tesoreria = usuario('Admin', 'Tesorería')
    expect(resolveVisualProfile(tesoreria)).toBe('TESORERIA')
    expect(keys('Admin', 'Tesorería', () => false)).toEqual([])
    expect(keys('Admin', 'Tesorería')).toEqual(['finanzas'])
  })
  it('normaliza Profesor', () => expect(resolveVisualProfile(usuario('Profesor'))).toBe('PROFESOR'))
  it('prioriza Regente para acceder a disciplina', () => expect(resolveVisualProfile(usuario('Admin', 'Regente'))).toBe('REGENTE'))
  it('normaliza Regente desde su rol', () => expect(resolveVisualProfile(usuario('Regente'))).toBe('REGENTE'))
  it('normaliza Tutor', () => expect(resolveVisualProfile(usuario('Tutor'))).toBe('TUTOR'))
  it('normaliza Estudiante', () => expect(resolveVisualProfile(usuario('Estudiante'))).toBe('ESTUDIANTE'))
  it('oculta todos los módulos FUTURE', () => expect(MODULE_CATALOG.filter((modulo) => modulo.estadoFuncional === 'FUTURE').every((modulo) => !keys('SuperAdmin').includes(modulo.key))).toBe(true))
  it('oculta todos los módulos DISABLED', () => expect(MODULE_CATALOG.filter((modulo) => modulo.estadoFuncional === 'DISABLED').every((modulo) => !keys('Admin').includes(modulo.key))).toBe(true))
  it('elimina grupos vacíos', () => expect(buildNavigation(usuario('Tutor'), () => true).every((grupo) => grupo.modulos.length > 0)).toBe(true))
  it('profesor ve asignaciones, horarios, evaluación, correcciones y comunicaciones', () => expect(keys('Profesor')).toEqual(['asignaciones', 'horarios', 'evaluacion', 'correcciones', 'comunicaciones', 'notificaciones']))
  it('horarios requieren permiso y no se muestran a familias o estudiantes', () => {
    expect(keys('Admin')).toContain('horarios')
    expect(keys('Admin', 'Director')).toContain('horarios')
    expect(keys('Admin', 'Secretaría')).toContain('horarios')
    expect(keys('SuperAdmin')).not.toContain('horarios')
    expect(keys('Admin', undefined, () => false)).not.toContain('horarios')
    expect(keys('Profesor', undefined, () => false)).not.toContain('horarios')
    expect(keys('Tutor')).not.toContain('horarios')
    expect(keys('Estudiante')).not.toContain('horarios')
  })
  it('muestra infraestructura a SuperAdmin, Director y Secretaría, pero oculta operaciones académicas al SuperAdmin', () => {
    expect(keys('SuperAdmin')).toContain('infraestructura')
    expect(keys('Admin', 'Director')).toContain('infraestructura')
    expect(keys('Admin', 'Secretaría')).toContain('infraestructura')
    expect(keys('SuperAdmin')).not.toEqual(expect.arrayContaining(['horarios', 'asistencia-registro', 'disciplina', 'evaluacion', 'correcciones']))
  })
  it('regente autorizado ve disciplina', () => expect(keys('Admin', 'Regente')).toContain('disciplina'))
  it('regente sin permiso no ve disciplina', () => expect(keys('Admin', 'Regente', () => false)).not.toContain('disciplina'))
  it('un administrador sin permisos conserva seguimiento y comunicaciones personales', () => expect(keys('Admin', undefined, () => false)).toEqual(['asistencia-consulta', 'asistencia-registro', 'historial-academico', 'riesgo-academico', 'comunicaciones', 'notificaciones']))
  it.each(['Director', 'Secretaría', 'Regente', 'Tutor', 'Estudiante', 'Profesor', 'Admin'])('ofrece comunicaciones personales a %s sin requerir permisos administrativos', rol => {
    expect(keys(rol, undefined, () => false)).toEqual(expect.arrayContaining(['comunicaciones', 'notificaciones']))
  })
  it('el conteo se deriva de los módulos visibles', () => { const grupos = buildNavigation(usuario('SuperAdmin'), () => true); expect(grupos.flatMap((grupo) => grupo.modulos)).toHaveLength(keys('SuperAdmin').length) })
  it('mantiene visibles las ocho HU del Sprint 1 para SuperAdmin', () => expect(keys('SuperAdmin')).toEqual(expect.arrayContaining(['institucion', 'usuarios', 'roles', 'gestiones', 'estructura', 'personal', 'estudiantes', 'inscripciones'])))
  it('muestra al Director las siete funcionalidades Sprint 1 de alcance colegial', () => expect(keys('Admin', 'Director')).toEqual(expect.arrayContaining(['institucion', 'usuarios', 'gestiones', 'estructura', 'personal', 'estudiantes', 'inscripciones'])))
  it('muestra Materias y plan de estudio solo a Director y Secretaría con permiso exacto', () => {
    expect(keys('Admin', 'Director')).toContain('materias-plan-estudio')
    expect(keys('Admin', 'Secretaría')).toContain('materias-plan-estudio')
    expect(keys('Profesor')).not.toContain('materias-plan-estudio')
    expect(keys('Admin', 'Regente')).not.toContain('materias-plan-estudio')
    expect(keys('Estudiante')).not.toContain('materias-plan-estudio')
    expect(keys('Admin', 'Director', () => false)).not.toContain('materias-plan-estudio')
  })
})

it('ofrece el portal familiar a Tutor y Estudiante en ámbito personal sin permisos administrativos', () => {
  for (const rol of ['Tutor', 'Estudiante']) {
    const user = usuario(rol)
    user.alcance!.tipo = 'PERSONAL'
    expect(buildNavigation(user, () => false).flatMap(group => group.modulos.map(modulo => modulo.key))).toContain('portal-familiar')
  }
  expect(keys('Profesor')).not.toContain('portal-familiar')
  expect(keys('SuperAdmin')).not.toContain('portal-familiar')
})
it('ofrece el panel institucional solo a Director autorizado', () => {
  expect(keys('Admin', 'Director')).toContain('panel-institucional')
  expect(keys('Admin', 'Director', () => false)).not.toContain('panel-institucional')
  expect(keys('SuperAdmin')).not.toContain('panel-institucional')
  expect(keys('Admin', 'Secretaría')).not.toContain('panel-institucional')
})

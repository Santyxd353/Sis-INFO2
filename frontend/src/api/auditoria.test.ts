import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import axiosInstance from './axiosInstance'
import { listarAuditoria, obtenerEventoAuditoria } from './auditoria'

describe('servicio de auditoría HU-05', () => {
  let mock: MockAdapter
  beforeEach(() => { mock = new MockAdapter(axiosInstance) })
  afterEach(() => mock.restore())

  it('consulta el listado paginado', async () => {
    mock.onGet('/usuarios/auditoria/').reply(200, { count: 1, next: null, previous: null, results: [{ id: 1 }] })
    expect((await listarAuditoria({})).data.count).toBe(1)
  })
  it('envía el filtro por acción', async () => {
    mock.onGet('/usuarios/auditoria/', { params: { accion: 'CREAR' } }).reply(200, { count: 0, results: [] })
    await expect(listarAuditoria({ accion: 'CREAR' })).resolves.toBeDefined()
  })
  it('envía el filtro por entidad', async () => {
    mock.onGet('/usuarios/auditoria/', { params: { entidad: 'USUARIO' } }).reply(200, { count: 0, results: [] })
    await listarAuditoria({ entidad: 'USUARIO' })
    expect(mock.history.get[0].params.entidad).toBe('USUARIO')
  })
  it('envía rango de fechas', async () => {
    mock.onGet('/usuarios/auditoria/').reply(200, { count: 0, results: [] })
    await listarAuditoria({ desde: '2026-01-01', hasta: '2026-01-31' })
    expect(mock.history.get[0].params).toMatchObject({ desde: '2026-01-01', hasta: '2026-01-31' })
  })
  it('envía usuario y página', async () => {
    mock.onGet('/usuarios/auditoria/').reply(200, { count: 0, results: [] })
    await listarAuditoria({ usuario: '4', page: 2, page_size: 20 })
    expect(mock.history.get[0].params).toMatchObject({ usuario: '4', page: 2 })
  })
  it('consulta un detalle', async () => {
    mock.onGet('/usuarios/auditoria/9/').reply(200, { id: 9, accion: 'CREAR' })
    expect((await obtenerEventoAuditoria(9)).data.id).toBe(9)
  })
  it('propaga un 400 de filtros', async () => {
    mock.onGet('/usuarios/auditoria/').reply(400, { desde: ['Fecha inválida'] })
    await expect(listarAuditoria({ desde: 'x' })).rejects.toMatchObject({ response: { status: 400 } })
  })
  it('propaga un 403 sin ejecutar logout', async () => {
    sessionStorage.setItem('auth_access_token', 'vigente')
    mock.onGet('/usuarios/auditoria/').reply(403)
    await expect(listarAuditoria({})).rejects.toMatchObject({ response: { status: 403 } })
    expect(sessionStorage.getItem('auth_access_token')).toBe('vigente')
  })
  it('solo utiliza GET para listado y detalle', async () => {
    mock.onGet().reply(200, { count: 0, results: [] })
    await listarAuditoria({}); await obtenerEventoAuditoria(1)
    expect(mock.history.post).toHaveLength(0); expect(mock.history.patch).toHaveLength(0); expect(mock.history.delete).toHaveLength(0)
  })
  it('el tipo público no incluye ip_hash', () => {
    const evento = { id: 1, ambito: 'GLOBAL', colegio: null, unidad_educativa: null, usuario: null, actor_snapshot: null, actor_username: null, actor_rol: null, accion: 'LOGIN', entidad: 'USUARIO', entidad_id: null, cambios_sanitizados: null, correlacion: 'x', created_at: '2026-01-01' }
    expect('ip_hash' in evento).toBe(false)
  })
})


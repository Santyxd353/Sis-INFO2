import { afterEach, describe, expect, it } from 'vitest'
import MockAdapter from 'axios-mock-adapter'
import api from './axiosInstance'
import { obtenerPortalFamiliar, obtenerPanelDirector, obtenerBoletin } from './portal'

const mock = new MockAdapter(api)
afterEach(() => { mock.reset(); sessionStorage.clear() })
describe('API del portal privado', () => {
  it('envía selección y señal al portal autenticado', async () => {
    sessionStorage.setItem('auth_access_token', 'token-prueba')
    const controller = new AbortController()
    mock.onGet('/portal/familia/').reply(200, { seleccionado: 8 })
    const response = await obtenerPortalFamiliar({ estudiante: 8, calendario_academico: 3, periodo: 4 }, controller.signal)
    expect(response.data.seleccionado).toBe(8)
    expect(mock.history.get[0].params).toEqual({ estudiante: 8, calendario_academico: 3, periodo: 4 })
    expect(mock.history.get[0].signal).toBe(controller.signal)
    expect(mock.history.get[0].headers?.Authorization).toBe('Bearer token-prueba')
  })
  it('mantiene 404 ajeno como error y no produce datos alternativos', async () => {
    mock.onGet('/portal/familia/').reply(404, { detail: 'No encontrado.' })
    await expect(obtenerPortalFamiliar({ estudiante: 999 })).rejects.toMatchObject({ response: { status: 404 } })
  })
  it('envía los filtros institucionales sin consultar listados de estudiantes', async () => {
    mock.onGet('/portal/panel-director/').reply(200, { indicadores: {} })
    await obtenerPanelDirector({ unidad_educativa: 2, calendario_academico: 3, periodo: 4 })
    expect(mock.history.get).toHaveLength(1)
    expect(mock.history.get[0].params).toEqual({ unidad_educativa: 2, calendario_academico: 3, periodo: 4 })
  })
  it('descarga boletín por endpoint privado y blob con JWT y cancelación', async () => {
    sessionStorage.setItem('auth_access_token', 'token-prueba')
    const controller = new AbortController(), pdf = new Blob(['%PDF'], { type: 'application/pdf' })
    mock.onGet('/estudiantes/documentos-academicos/5/descargar/').reply(200, pdf)
    expect(await obtenerBoletin(5, controller.signal)).toBe(pdf)
    expect(mock.history.get[0].responseType).toBe('blob')
    expect(mock.history.get[0].signal).toBe(controller.signal)
    expect(mock.history.get[0].headers?.Authorization).toBe('Bearer token-prueba')
  })
})

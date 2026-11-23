import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import axiosInstance, { authAxios, resetRefreshStateForTests } from './axiosInstance'
import { AUTH_ACCESS_TOKEN_KEY, AUTH_REFRESH_TOKEN_KEY, saveSession } from './auth'
import { testUser } from '../test/fixtures'

const apiMock = new MockAdapter(axiosInstance)
const authMock = new MockAdapter(authAxios)

describe('cliente HTTP protegido', () => {
  beforeEach(() => {
    apiMock.reset()
    authMock.reset()
    resetRefreshStateForTests()
    saveSession({ access: 'access-old', refresh: 'refresh-old', user: testUser })
  })

  afterEach(() => resetRefreshStateForTests())

  it('envía el access token como Bearer', async () => {
    apiMock.onGet('/recurso/').reply((config) => [200, { authorization: config.headers?.Authorization }])
    const response = await axiosInstance.get<{ authorization: string }>('/recurso/')
    expect(response.data.authorization).toBe('Bearer access-old')
  })

  it('envía la fecha y zona horaria declaradas por el cliente', async () => {
    apiMock.onGet('/metadatos/').reply((config) => [200, {
      fecha: config.headers?.['X-Client-Time'],
      zona: config.headers?.['X-Client-Timezone'],
    }])
    const response = await axiosInstance.get<{ fecha: string; zona: string }>('/metadatos/')
    expect(response.data.fecha).toMatch(/^\d{4}-\d{2}-\d{2}T/)
    expect(response.data.zona).toBeTruthy()
  })

  it('renueva ante 401, guarda tokens rotados y reintenta una vez', async () => {
    let attempts = 0
    apiMock.onGet('/recurso/').reply(() => ++attempts === 1 ? [401] : [200, { ok: true }])
    authMock.onPost('/usuarios/refresh/', { refresh: 'refresh-old' })
      .reply(200, { access: 'access-new', refresh: 'refresh-new' })

    await expect(axiosInstance.get('/recurso/')).resolves.toMatchObject({ data: { ok: true } })
    expect(attempts).toBe(2)
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access-new')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('refresh-new')
  })

  it('comparte una única renovación entre varios 401 simultáneos', async () => {
    let refreshCalls = 0
    apiMock.onGet(/\/recurso\/[12]\//).reply((config) =>
      config.headers?.Authorization === 'Bearer access-new' ? [200, { ok: true }] : [401],
    )
    authMock.onPost('/usuarios/refresh/').reply(() => {
      refreshCalls += 1
      return [200, { access: 'access-new', refresh: 'refresh-new' }]
    })

    await Promise.all([axiosInstance.get('/recurso/1/'), axiosInstance.get('/recurso/2/')])
    expect(refreshCalls).toBe(1)
  })

  it('limpia la sesión si el refresh es inválido', async () => {
    window.history.replaceState({}, '', '/login')
    apiMock.onGet('/recurso/').reply(401)
    authMock.onPost('/usuarios/refresh/').reply(401)

    await expect(axiosInstance.get('/recurso/')).rejects.toBeDefined()
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBeNull()
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBeNull()
  })

  it('no renueva ni elimina la sesión ante un 403', async () => {
    apiMock.onGet('/prohibido/').reply(403)
    await expect(axiosInstance.get('/prohibido/')).rejects.toMatchObject({ response: { status: 403 } })
    expect(authMock.history.post).toHaveLength(0)
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access-old')
  })
})

import MockAdapter from 'axios-mock-adapter'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import axiosInstance, { authAxios } from '../../api/axiosInstance'
import { AUTH_ACCESS_TOKEN_KEY, AUTH_REFRESH_TOKEN_KEY, saveSession } from '../../api/auth'
import { testUser } from '../../test/fixtures'
import { dashboardPath } from '../routes/dashboardPath'
import { AuthProvider, useAuth } from './AuthContext'

const wrapper = ({ children }: { children: ReactNode }) => <AuthProvider>{children}</AuthProvider>

describe('AuthContext', () => {
  it('inicia sesión con email/password y persiste ambos tokens', async () => {
    const mock = new MockAdapter(authAxios)
    mock.onPost('/usuarios/login/', { email: testUser.email, password: 'secret' })
      .reply(200, { access: 'access', refresh: 'refresh', user: testUser })
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(() => result.current.login(testUser.email, 'secret'))
    expect(result.current.user).toEqual(testUser)
    expect(result.current.user?.alcance?.tipo).toBe('GLOBAL')
    expect(result.current.user?.permisos_efectivos).toEqual([])
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('refresh')
    mock.restore()
  })

  it('inicia sesión con username/password sin alterar el flujo JWT', async () => {
    const mock = new MockAdapter(authAxios)
    mock.onPost('/usuarios/login/', { username: testUser.username, password: 'secret' })
      .reply(200, { access: 'access-user', refresh: 'refresh-user', user: testUser })
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(() => result.current.login(`  ${testUser.username}  `, 'secret'))
    expect(result.current.user).toEqual(testUser)
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access-user')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('refresh-user')
    mock.restore()
  })

  it('restaura el usuario consultando el perfil', async () => {
    saveSession({ access: 'access', refresh: 'refresh', user: testUser })
    const mock = new MockAdapter(axiosInstance)
    mock.onGet('/usuarios/perfil/').reply(200, testUser)
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.user).toEqual(testUser)
    expect(mock.history.get.filter((request) => request.url === '/usuarios/perfil/')).toHaveLength(1)
    mock.restore()
  })

  it('inicia y restaura Tesorería como Admin con su ruta y sin permisos implícitos', async () => {
    const tesoreria = {
      ...testUser,
      rol: { id: 2, nombre: 'Admin' },
      perfil: { tipo: 'admin', puesto: { id: 9, nombre: 'Tesorería' } },
      alcance: { tipo: 'COLEGIO' as const, colegio_id: 8, colegio_nombre: 'Colegio', unidad_id: null, unidad_nombre: null },
      permisos_efectivos: [], permisos_ui: [],
    }
    const authMock = new MockAdapter(authAxios)
    authMock.onPost('/usuarios/login/').reply(200, { access: 'tes-access', refresh: 'tes-refresh', user: tesoreria })
    const login = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(login.result.current.loading).toBe(false))
    await act(() => login.result.current.login(tesoreria.email, 'secret'))
    expect(dashboardPath(login.result.current.user)).toBe('/dashboard/tesoreria')
    expect(login.result.current.can('usuario', 'listar')).toBe(false)
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('tes-access')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('tes-refresh')
    authMock.restore()

    saveSession({ access: 'restore-access', refresh: 'restore-refresh', user: tesoreria })
    const apiMock = new MockAdapter(axiosInstance)
    apiMock.onGet('/usuarios/perfil/').reply(200, tesoreria)
    const restored = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(restored.result.current.loading).toBe(false))
    expect(dashboardPath(restored.result.current.user)).toBe('/dashboard/tesoreria')
    apiMock.onGet('/tesoreria/privado/').reply(403)
    const refreshMock = new MockAdapter(authAxios)
    refreshMock.onPost('/usuarios/refresh/').reply(200, {})
    refreshMock.onPost('/usuarios/logout/').reply(200, {})
    await expect(axiosInstance.get('/tesoreria/privado/')).rejects.toMatchObject({ response: { status: 403 } })
    expect(restored.result.current.user).toEqual(tesoreria)
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('restore-access')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('restore-refresh')
    expect(refreshMock.history.post).toHaveLength(0)
    apiMock.restore()
    refreshMock.restore()
  })

  it('autoriza solamente permisos efectivos exactos para usuarios institucionales', async () => {
    const admin = {
      ...testUser,
      rol: { id: 2, nombre: 'Admin' },
      alcance: { tipo: 'COLEGIO' as const, colegio_id: 3, colegio_nombre: 'Colegio', unidad_id: null, unidad_nombre: null },
      permisos_efectivos: [{ modelo: 'auditoria', accion: 'listar' }],
    }
    const mock = new MockAdapter(authAxios)
    mock.onPost('/usuarios/login/').reply(200, { access: 'access', refresh: 'refresh', user: admin })
    const { result } = renderHook(() => useAuth(), { wrapper })
    await act(() => result.current.login(admin.email, 'secret'))
    expect(result.current.can('auditoria', 'listar')).toBe(true)
    expect(result.current.can('auditoria', 'editar')).toBe(false)
    expect(result.current.can('usuario', 'listar')).toBe(false)
    mock.restore()
  })

  it('una respuesta antigua sin permisos efectivos no obtiene concesiones por defecto', async () => {
    const legacy = { ...testUser, rol: { id: 2, nombre: 'Admin' }, alcance: undefined, permisos_efectivos: undefined }
    const mock = new MockAdapter(authAxios)
    mock.onPost('/usuarios/login/').reply(200, { access: 'access', refresh: 'refresh', user: legacy })
    const { result } = renderHook(() => useAuth(), { wrapper })
    await act(() => result.current.login(legacy.email, 'secret'))
    expect(result.current.can('usuario', 'listar')).toBe(false)
    mock.restore()
  })

  it('permisos de interfaz aplican opt-out de visibilidad y denegación por defecto de edición (HU-SE02)', async () => {
    const usuario = {
      ...testUser,
      rol: { id: 2, nombre: 'Admin' },
      alcance: { tipo: 'COLEGIO' as const, colegio_id: 3, colegio_nombre: 'Colegio', unidad_id: null, unidad_nombre: null },
      permisos_ui: [
        { componente: 'boton-matricular', visible: false, editable: false },
        { componente: 'panel-notas', visible: true, editable: true },
      ],
    }
    const mock = new MockAdapter(authAxios)
    mock.onPost('/usuarios/login/').reply(200, { access: 'access', refresh: 'refresh', user: usuario })
    const { result } = renderHook(() => useAuth(), { wrapper })
    await act(() => result.current.login(usuario.email, 'secret'))
    expect(result.current.puedeComponente('boton-matricular')).toBe(false)
    expect(result.current.puedeEditarComponente('boton-matricular')).toBe(false)
    expect(result.current.puedeComponente('panel-notas')).toBe(true)
    expect(result.current.puedeEditarComponente('panel-notas')).toBe(true)
    // Sin configuración: visible por defecto, no editable por defecto.
    expect(result.current.puedeComponente('componente-nuevo')).toBe(true)
    expect(result.current.puedeEditarComponente('componente-nuevo')).toBe(false)
    mock.restore()
  })

  it('el superadmin global conserva todos los componentes visibles y editables', async () => {
    const mock = new MockAdapter(authAxios)
    mock.onPost('/usuarios/login/').reply(200, { access: 'access', refresh: 'refresh', user: testUser })
    const { result } = renderHook(() => useAuth(), { wrapper })
    await act(() => result.current.login(testUser.email, 'secret'))
    expect(result.current.puedeComponente('cualquier-componente')).toBe(true)
    expect(result.current.puedeEditarComponente('cualquier-componente')).toBe(true)
    mock.restore()
  })

  it('envía refresh al cerrar sesión y siempre limpia credenciales', async () => {
    saveSession({ access: 'access', refresh: 'refresh', user: testUser })
    const mock = new MockAdapter(axiosInstance)
    mock.onGet('/usuarios/perfil/').reply(200, testUser)
    mock.onPost('/usuarios/logout/', { refresh: 'refresh' }).reply(500)
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.user).toEqual(testUser))
    await act(() => result.current.logout())
    expect(mock.history.post[0].data).toBe(JSON.stringify({ refresh: 'refresh' }))
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBeNull()
    expect(result.current.user).toBeNull()
    mock.restore()
  })
})

import MockAdapter from 'axios-mock-adapter'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import axiosInstance, { authAxios } from '../../api/axiosInstance'
import { AUTH_ACCESS_TOKEN_KEY, AUTH_REFRESH_TOKEN_KEY, saveSession } from '../../api/auth'
import { testUser } from '../../test/fixtures'
import { AuthProvider, useAuth } from '../contexts/AuthContext'
import { buildNavigation } from '../navigation/navigationConfig'
import RequireAuth from './RequireAuth'
import RequireReportes from './RequireReportes'

const mock = new MockAdapter(axiosInstance)
const authMock = new MockAdapter(authAxios)
const operativo = [{ modelo: 'reporte-definicion', accion: 'listar' }, { modelo: 'reporte-ejecucion', accion: 'ejecutar' }]
const qbe = [{ modelo: 'reporte-qbe', accion: 'validar' }, { modelo: 'reporte-qbe', accion: 'ejecutar' }]
function Menu() {
  const { user, can } = useAuth()
  return <div>{JSON.stringify(buildNavigation(user, can)).includes('/dashboard/reportes') && <span>Menú reportes</span>}</div>
}
function pantalla() {
  return render(<MemoryRouter initialEntries={['/dashboard/reportes']}><AuthProvider><Menu /><Routes>
    <Route path="/dashboard/reportes" element={<RequireAuth><RequireReportes /></RequireAuth>} />
    <Route path="/no-permission" element={<p>Acceso denegado</p>} />
    <Route path="/login" element={<p>Iniciar sesión</p>} />
  </Routes></AuthProvider></MemoryRouter>)
}
describe('acceso directo a reportes', () => {
  beforeEach(() => {
    sessionStorage.clear(); mock.reset(); authMock.reset()
    mock.onGet('/reportes/catalogo/').reply(200, { results: [] })
    mock.onGet('/reportes/definiciones/').reply(200, { results: [] })
    mock.onGet('/reportes/qbe/catalogo/').reply(200, { results: [] })
    mock.onGet('/reportes/qbe/definiciones/').reply(200, { results: [] })
    mock.onGet('/calendario/calendarios/').reply(200, [])
    mock.onGet('/academico/cursos/').reply(200, [])
  })
  afterEach(() => mock.reset())
  const ingresar = (rol: string, permisos: typeof operativo, tipo: 'COLEGIO' | 'UNIDAD' | 'GLOBAL' = 'COLEGIO') => {
    const user = { ...testUser, rol: { id: 2, nombre: rol }, alcance: { tipo, colegio_id: tipo === 'GLOBAL' ? null : 1, colegio_nombre: 'Colegio', unidad_id: tipo === 'UNIDAD' ? 1 : null, unidad_nombre: null }, permisos_efectivos: permisos }
    saveSession({ access: 'access', refresh: 'refresh', user })
    mock.onGet('/usuarios/perfil/').reply(200, user)
    pantalla()
  }
  it.each([
    ['Director', [...operativo, ...qbe], true, true],
    ['Director', operativo, true, false],
    ['Director', qbe, false, true],
    ['Secretaria', operativo, true, false],
  ])('autoriza %s según permisos efectivos', async (rol, permisos, verOperativo, verQbe) => {
    ingresar(rol, permisos)
    expect(await screen.findByText('Menú reportes')).toBeInTheDocument()
    await screen.findByRole('heading', { name: 'Reportes académicos' })
    expect(Boolean(screen.queryByRole('heading', { name: 'Reportes operativos' }))).toBe(verOperativo)
    expect(Boolean(screen.queryByRole('tab', { name: 'Consulta personalizada' }))).toBe(verQbe)
    if (verQbe) {
      fireEvent.click(screen.getByRole('tab', { name: 'Consulta personalizada' }))
      expect(screen.getByRole('heading', { name: 'Consulta personalizada (QBE)' })).toBeInTheDocument()
    }
  })
  it.each(['Secretaria', 'Profesor', 'Tutor', 'Estudiante', 'SuperAdmin'])('deniega %s sin permiso aplicable', async (rol) => {
    ingresar(rol, rol === 'Secretaria' || rol === 'SuperAdmin' ? [] : [...operativo, ...qbe], rol === 'SuperAdmin' ? 'GLOBAL' : 'COLEGIO')
    expect(await screen.findByText('Acceso denegado')).toBeInTheDocument()
    expect(screen.queryByText('Menú reportes')).not.toBeInTheDocument()
    expect(mock.history.get.some((r) => r.url?.startsWith('/reportes/'))).toBe(false)
  })
  it('redirige al login sin autenticación', async () => {
    pantalla()
    await waitFor(() => expect(screen.getByText('Iniciar sesión')).toBeInTheDocument())
    expect(mock.history.get.some((r) => r.url?.startsWith('/reportes/'))).toBe(false)
  })
  it('conserva la sesión cuando el catálogo responde 403', async () => {
    mock.onGet('/reportes/catalogo/').reply(403, { detail: 'Prohibido' })
    ingresar('Director', operativo)
    expect(await screen.findByText('No tiene permiso para este reporte.')).toBeInTheDocument()
    expect(screen.getByText('Menú reportes')).toBeInTheDocument()
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('refresh')
    expect(sessionStorage.getItem('auth_user')).not.toBeNull()
    expect(authMock.history.post).toHaveLength(0)
    expect(screen.queryByText('Iniciar sesión')).not.toBeInTheDocument()
  })
  it('monta solo la pestaña activa y conserva la sesión al navegar', async () => {
    ingresar('Director', [...operativo, ...qbe])
    await screen.findByRole('heading', { name: 'Reportes operativos' })
    expect(mock.history.get.some(r => r.url?.startsWith('/reportes/qbe/'))).toBe(false)
    expect(screen.queryByRole('heading', { name: 'Consulta personalizada (QBE)' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Consulta personalizada' }))
    expect(screen.queryByRole('heading', { name: 'Reportes operativos' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Consulta personalizada (QBE)' })).toBeInTheDocument()
    await waitFor(() => expect(mock.history.get.some(r => r.url === '/reportes/qbe/catalogo/')).toBe(true))
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('refresh')
    expect(sessionStorage.getItem('auth_user')).not.toBeNull()
    expect(screen.getByRole('tab', { name: 'Historial' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Boletines' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Centralizador' })).toBeInTheDocument()
  })
  it('conserva la sesión activa cuando el historial responde 403', async () => {
    mock.onGet('/reportes/ejecuciones/').reply(403, { detail: 'Prohibido' })
    ingresar('Director', operativo)
    const access = sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)
    const refresh = sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)
    const usuario = sessionStorage.getItem('auth_user')
    fireEvent.click(await screen.findByRole('tab', { name: 'Historial' }))
    expect(await screen.findByText(/No tiene permiso para consultar el historial/)).toBeInTheDocument()
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe(access)
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe(refresh)
    expect(sessionStorage.getItem('auth_user')).toBe(usuario)
    expect(access).toBe('access')
    expect(refresh).toBe('refresh')
    expect(usuario).not.toBeNull()
    expect(screen.getByText('Menú reportes')).toBeInTheDocument()
    expect(screen.queryByText('Iniciar sesión')).not.toBeInTheDocument()
    expect(authMock.history.post).toHaveLength(0)
    expect(mock.history.post.some((request) => request.url?.includes('logout'))).toBe(false)
  })
  it.each(['previsualizar', 'exportar', 'qbe'])('conserva la sesión ante 403 en %s', async (caso) => {
    const fuente = { codigo: 'ESTUDIANTES', nombre: 'Alumnos', etiqueta: 'Alumnos', columnas: [{ campo: 'nombre', etiqueta: 'Nombre', tipo: 'texto' }], predeterminadas: ['nombre'], filtros: [], ordenables: [] }
    if (caso === 'qbe') {
      mock.onGet('/reportes/qbe/catalogo/').reply(200, { results: [fuente] })
      mock.onGet('/reportes/qbe/definiciones/').reply(200, { results: [{ id: 2, codigo_fuente: 'ESTUDIANTES' }] })
      mock.onPost('/reportes/qbe/definiciones/').reply(403)
    } else {
      mock.onGet('/reportes/catalogo/').reply(200, { results: [fuente] })
      mock.onGet('/reportes/definiciones/').reply(200, { results: [{ id: 1, codigo_fuente: 'ESTUDIANTES' }] })
      mock.onPatch('/reportes/definiciones/1/').reply(200, { id: 1 })
      mock.onPost(`/reportes/${caso}/`).reply(403)
    }
    ingresar('Director', caso === 'qbe' ? qbe : operativo)
    await screen.findByText('Alumnos')
    fireEvent.click(screen.getByRole('button', { name: caso === 'exportar' ? 'CSV' : 'Vista previa' }))
    expect(await screen.findByText('No tiene permiso para este reporte.')).toBeInTheDocument()
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('refresh')
    expect(sessionStorage.getItem('auth_user')).not.toBeNull()
    expect(authMock.history.post).toHaveLength(0)
    expect(screen.getByText('Menú reportes')).toBeInTheDocument()
  })
})

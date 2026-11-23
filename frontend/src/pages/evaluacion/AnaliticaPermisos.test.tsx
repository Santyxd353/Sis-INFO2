import { fireEvent, render, screen } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import { expect, it, vi } from 'vitest'
import AnaliticaPanel from './AnaliticaPanel'
import axiosInstance, { authAxios } from '../../api/axiosInstance'
import { AUTH_ACCESS_TOKEN_KEY, AUTH_REFRESH_TOKEN_KEY, AUTH_SESSION_CLEARED_EVENT, AUTH_USER_KEY } from '../../api/auth'

vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: { alcance: { tipo: 'COLEGIO', colegio_id: 1 } } }) }))
vi.mock('../../api/catalogosInstitucionales', () => ({ listarUnidadesCatalogo: vi.fn(async () => [{ id: 1, nombre: 'Unidad A' }]) }))
vi.mock('../../api/asignacionesDocentes', () => ({ listarCalendarios: vi.fn(async () => [{ id: 3, año: 2026 }]), listarCursos: vi.fn(async () => []), listarMateriasCurso: vi.fn(async () => []) }))

it('muestra 403 de analítica sin alterar la sesión ni solicitar refresh o logout', async () => {
  const api = new MockAdapter(axiosInstance)
  const auth = new MockAdapter(authAxios)
  const sesion = vi.fn()
  const usuario = JSON.stringify({ id: 5, nombre: 'Director' })
  sessionStorage.setItem(AUTH_ACCESS_TOKEN_KEY, 'access-prueba')
  sessionStorage.setItem(AUTH_REFRESH_TOKEN_KEY, 'refresh-prueba')
  sessionStorage.setItem(AUTH_USER_KEY, usuario)
  window.addEventListener(AUTH_SESSION_CLEARED_EVENT, sesion)
  const ruta = window.location.href
  api.onGet('/calendario/periodos/').reply(200, [])
  api.onGet('/reportes/analitica/resumen/').reply(403)
  try {
    render(<AnaliticaPanel onExportado={() => {}} />)
    await screen.findByRole('option', { name: 'Unidad A' })
    fireEvent.change(screen.getByLabelText('Unidad educativa'), { target: { value: '1' } })
    await screen.findByRole('option', { name: '2026' })
    fireEvent.change(screen.getByLabelText('Gestión'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar / actualizar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No tiene permiso para consultar analítica.')
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access-prueba')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('refresh-prueba')
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBe(usuario)
    expect(auth.history.post).toHaveLength(0)
    expect(api.history.post.some(r => r.url?.includes('logout'))).toBe(false)
    expect(sesion).not.toHaveBeenCalled()
    expect(window.location.href).toBe(ruta)
  } finally {
    api.restore(); auth.restore(); window.removeEventListener(AUTH_SESSION_CLEARED_EVENT, sesion)
    sessionStorage.removeItem(AUTH_ACCESS_TOKEN_KEY); sessionStorage.removeItem(AUTH_REFRESH_TOKEN_KEY); sessionStorage.removeItem(AUTH_USER_KEY)
  }
})

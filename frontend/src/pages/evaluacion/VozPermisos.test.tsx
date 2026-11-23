import { fireEvent, render, screen } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import { expect, it, vi } from 'vitest'
import VozPanel from './VozPanel'
import axiosInstance, { authAxios } from '../../api/axiosInstance'
import { AUTH_ACCESS_TOKEN_KEY, AUTH_REFRESH_TOKEN_KEY, AUTH_SESSION_CLEARED_EVENT, AUTH_USER_KEY } from '../../api/auth'

it('un 403 de voz conserva la sesión sin refresh, logout ni redirección', async () => {
  const api = new MockAdapter(axiosInstance)
  const auth = new MockAdapter(authAxios)
  const sesion = vi.fn()
  const usuario = JSON.stringify({ id: 5, nombre: 'Director' })
  sessionStorage.setItem(AUTH_ACCESS_TOKEN_KEY, 'access-prueba')
  sessionStorage.setItem(AUTH_REFRESH_TOKEN_KEY, 'refresh-prueba')
  sessionStorage.setItem(AUTH_USER_KEY, usuario)
  window.addEventListener(AUTH_SESSION_CLEARED_EVENT, sesion)
  const ruta = window.location.href
  api.onPost('/reportes/voz/interpretar/').reply(403)
  try {
    render(<VozPanel contexto={{ unidad_educativa: 1, calendario_academico: 2 }} onExportado={() => {}} />)
    fireEvent.change(screen.getByLabelText('Solicitud'), { target: { value: 'Consulta la asistencia' } })
    fireEvent.click(screen.getByRole('button', { name: 'Interpretar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No tiene permiso')
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

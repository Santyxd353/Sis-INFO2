import MockAdapter from 'axios-mock-adapter'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import axiosInstance from '../../api/axiosInstance'
import { saveSession } from '../../api/auth'
import { AuthProvider } from '../contexts/AuthContext'
import { testUser } from '../../test/fixtures'
import RequireAuth from './RequireAuth'

const mock = new MockAdapter(axiosInstance)

const renderRoutes = () => render(
  <MemoryRouter initialEntries={['/privado']}>
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<p>Página de acceso</p>} />
        <Route path="/privado" element={<RequireAuth><p>Contenido privado</p></RequireAuth>} />
      </Routes>
    </AuthProvider>
  </MemoryRouter>,
)

describe('RequireAuth', () => {
  afterEach(() => mock.reset())

  it('espera la restauración y redirige al login sin sesión', async () => {
    renderRoutes()
    expect(await screen.findByText('Página de acceso')).toBeInTheDocument()
    expect(screen.queryByText('Contenido privado')).not.toBeInTheDocument()
  })

  it('permite la ruta después de restaurar una sesión válida', async () => {
    saveSession({ access: 'access', refresh: 'refresh', user: testUser })
    mock.onGet('/usuarios/perfil/').reply(200, testUser)
    renderRoutes()
    expect(screen.getByText('Cargando panel...')).toBeInTheDocument()
    expect(await screen.findByText('Contenido privado')).toBeInTheDocument()
  })
})

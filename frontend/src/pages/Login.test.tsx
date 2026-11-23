import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import Login from './Login'
import { useAuth } from '../app/contexts/AuthContext'

vi.mock('../app/contexts/AuthContext', () => ({ useAuth: vi.fn() }))

function DestinoSuscripciones() {
  return <p>{useLocation().search}</p>
}

function enviarCredenciales() {
  fireEvent.change(screen.getByPlaceholderText('nombre@colegio.edu o usuario'), { target: { value: 'usuario@example.test' } })
  fireEvent.change(document.querySelector('input[autocomplete="current-password"]')!, { target: { value: 'test-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Ingresar al sistema' }))
}

describe('redirección después del login', () => {
  afterEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('no envía a Suscripciones a un tutor por una selección de plan guardada', async () => {
    localStorage.setItem('plan_seleccionado', '2')
    vi.mocked(useAuth).mockReturnValue({
      login: vi.fn().mockResolvedValue({ rol: { nombre: 'Tutor' } }),
    } as never)

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard/tutor" element={<p>Portal tutor</p>} />
          <Route path="/dashboard/suscripciones" element={<p>Suscripciones</p>} />
        </Routes>
      </MemoryRouter>,
    )

    enviarCredenciales()

    expect(await screen.findByText('Portal tutor')).toBeInTheDocument()
    expect(screen.queryByText('Suscripciones')).not.toBeInTheDocument()
    expect(localStorage.getItem('plan_seleccionado')).toBeNull()
  })

  it.each(['confirmacion', 'cancelado'])('conserva el retorno de Stripe con estado %s', async (estado) => {
    localStorage.setItem('plan_seleccionado', '2')
    vi.mocked(useAuth).mockReturnValue({
      login: vi.fn().mockResolvedValue({ rol: { nombre: 'Director' } }),
    } as never)
    const retorno = `?stripe=${estado}`

    render(
      <MemoryRouter initialEntries={[{
        pathname: '/login',
        state: { from: { pathname: '/dashboard/suscripciones', search: retorno } },
      }]}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard/suscripciones" element={<DestinoSuscripciones />} />
        </Routes>
      </MemoryRouter>,
    )
    enviarCredenciales()

    expect(await screen.findByText(retorno)).toBeInTheDocument()
  })
})

import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from '../contexts/AuthContext'
import RequireProfile from './RequireProfile'

vi.mock('../contexts/AuthContext', () => ({ useAuth: vi.fn() }))

describe('protección de perfil Tesorería', () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      loading: false,
      user: {
        rol: { id: 2, nombre: 'Admin' },
        perfil: { tipo: 'admin', puesto: { id: 9, nombre: 'Tesorería' } },
      },
    } as unknown as ReturnType<typeof useAuth>)
  })

  it('admite Tesorería y rechaza un puesto diferente', () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={['/tesoreria']}>
        <Routes>
          <Route path="/tesoreria" element={<RequireProfile profiles={['TESORERIA']}><div>Panel Tesorería</div></RequireProfile>} />
          <Route path="/dashboard/no-permission" element={<div>Acceso restringido</div>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('Panel Tesorería')).toBeInTheDocument()
    vi.mocked(useAuth).mockReturnValue({
      loading: false,
      user: { rol: { id: 2, nombre: 'Admin' }, perfil: { tipo: 'admin', puesto: { id: 1, nombre: 'Secretaría' } } },
    } as unknown as ReturnType<typeof useAuth>)
    rerender(
      <MemoryRouter initialEntries={['/tesoreria']}>
        <Routes>
          <Route path="/tesoreria" element={<RequireProfile profiles={['TESORERIA']}><div>Panel Tesorería</div></RequireProfile>} />
          <Route path="/dashboard/no-permission" element={<div>Acceso restringido</div>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('Acceso restringido')).toBeInTheDocument()
  })
})

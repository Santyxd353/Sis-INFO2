import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from '../contexts/AuthContext'
import type { Usuario } from '../modelos/Usuarios'
import RequirePermission from './RequirePermission'

vi.mock('../contexts/AuthContext', () => ({ useAuth: vi.fn() }))

const baseUser = {
  rol: { id: 1, nombre: 'Admin' },
  alcance: { tipo: 'COLEGIO', colegio_id: 1, colegio_nombre: 'Colegio', unidad_id: null, unidad_nombre: null },
  permisos_efectivos: [],
} as unknown as Usuario

const renderGuard = (props: Partial<React.ComponentProps<typeof RequirePermission>> = {}) => render(
  <MemoryRouter initialEntries={['/protegida']}>
    <Routes>
      <Route path="/protegida" element={<RequirePermission modelos={['auditoria']} {...props}><div>Contenido autorizado</div></RequirePermission>} />
      <Route path="/no-permission" element={<div>Acceso restringido</div>} />
    </Routes>
  </MemoryRouter>,
)

describe('protección directa por perfil, alcance y permiso efectivo', () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      user: baseUser,
      can: () => false,
      isProfesor: () => false,
      permisosCargando: false,
    } as unknown as ReturnType<typeof useAuth>)
  })

  it('permite el recurso cuando existe el permiso exacto', () => {
    vi.mocked(useAuth).mockReturnValue({ ...useAuth(), can: (modelo:string, accion:string) => modelo === 'auditoria' && accion === 'listar' } as ReturnType<typeof useAuth>)
    renderGuard()
    expect(screen.getByText('Contenido autorizado')).toBeInTheDocument()
  })

  it('no concede acceso por el rol Admin genérico', () => {
    renderGuard()
    expect(screen.getByText('Acceso restringido')).toBeInTheDocument()
  })

  it('rechaza un perfil que no está autorizado aunque tenga permiso', () => {
    vi.mocked(useAuth).mockReturnValue({ ...useAuth(), can: () => true } as ReturnType<typeof useAuth>)
    renderGuard({ profiles: ['DIRECTOR'] })
    expect(screen.getByText('Acceso restringido')).toBeInTheDocument()
  })

  it('rechaza un alcance incompatible aunque tenga permiso', () => {
    vi.mocked(useAuth).mockReturnValue({ ...useAuth(), can: () => true } as ReturnType<typeof useAuth>)
    renderGuard({ scopes: ['UNIDAD'] })
    expect(screen.getByText('Acceso restringido')).toBeInTheDocument()
  })

  it('admite la excepción de solo lectura para profesor con alcance PERSONAL', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { ...baseUser, rol: { id: 2, nombre: 'Profesor' }, alcance: { ...baseUser.alcance!, tipo: 'PERSONAL' } },
      can: () => false,
      isProfesor: () => true,
      permisosCargando: false,
    } as unknown as ReturnType<typeof useAuth>)
    renderGuard({ modelos: ['asignacion-docente'], allowPersonalProfessor: true, profiles: ['PROFESOR'], scopes: ['PERSONAL'] })
    expect(screen.getByText('Contenido autorizado')).toBeInTheDocument()
  })
})

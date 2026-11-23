import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FunctionalDashboardLayout from './FunctionalDashboardLayout'

let rol = 'SuperAdmin'

vi.mock('../../app/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: {
      rol: { nombre: rol },
      unidad: null,
      alcance: rol.toLowerCase() === 'superadmin'
        ? { tipo: 'GLOBAL' }
        : { tipo: 'PERSONAL', colegio_id: 1, unidad_id: 2 },
    },
    can: () => true,
    isSuperAdmin: () => rol.toLowerCase() === 'superadmin',
    isAdmin: () => ['superadmin', 'admin'].includes(rol.toLowerCase()),
  }),
}))

vi.mock('./RoleLayout', () => ({
  default: ({ modulos, basePath, titulo }: { modulos: Array<{ titulo: string }>; basePath: string; titulo: string }) => (
    <nav aria-label={titulo} data-base={basePath}>{modulos.map((modulo) => <span key={modulo.titulo}>{modulo.titulo}</span>)}</nav>
  ),
}))

describe('menú de las rutas funcionales', () => {
  beforeEach(() => { rol = 'SuperAdmin' })

  it('conserva todos los módulos cuando el usuario real es SuperAdmin', () => {
    render(<FunctionalDashboardLayout />)
    expect(screen.getByText('Configuración institucional')).toBeInTheDocument()
    expect(screen.getByText('Seguridad y auditoría')).toBeInTheDocument()
    expect(screen.queryByText('Asignaciones docentes')).not.toBeInTheDocument()
  })

  it('limita el menú solamente cuando el rol real es Profesor', () => {
    rol = 'Profesor'
    render(<FunctionalDashboardLayout />)
    expect(screen.getByText('Asignaciones docentes')).toBeInTheDocument()
    expect(screen.queryByText('Configuración institucional')).not.toBeInTheDocument()
  })
  it.each([
    ['Tutor', '/dashboard/tutor', 'Portal de Tutor'],
    ['Estudiante', '/dashboard/estudiante', 'Portal del Estudiante'],
    ['Regente', '/dashboard/regente', 'Panel de Regencia'],
  ])('conserva identidad y regreso al portal de %s en las rutas compartidas', (role, base, title) => {
    rol = role
    render(<FunctionalDashboardLayout />)
    expect(screen.getByRole('navigation', { name: title })).toHaveAttribute('data-base', base)
    expect(screen.getByText('Comunicados')).toBeInTheDocument()
    expect(screen.getByText('Notificaciones')).toBeInTheDocument()
  })
})

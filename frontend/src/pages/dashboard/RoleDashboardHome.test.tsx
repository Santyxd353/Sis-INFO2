import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import RoleDashboardHome from './RoleDashboardHome'
let permit = true
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, rol: { nombre: 'Director' }, alcance: { tipo: 'COLEGIO', colegio_id: 1, colegio_nombre: 'Colegio Central' } }, can: () => permit }) }))
vi.mock('../../api/dashboard', () => ({ loadDashboardMetrics: () => Promise.resolve([]), loadRecentAudit: () => Promise.resolve([]) }))
describe('inicio del director', () => {
  it('ofrece el panel institucional aunque otras acciones ocupen el resumen', async () => {
    render(<MemoryRouter><RoleDashboardHome profile="DIRECTOR" basePath="/dashboard/director" /></MemoryRouter>)
    expect(await screen.findByRole('link', { name: /Panel institucional/ })).toHaveAttribute('href', '/dashboard/panel-institucional')
  })
  it('oculta el acceso cuando falta el permiso', () => {
    permit = false
    render(<MemoryRouter><RoleDashboardHome profile="DIRECTOR" basePath="/dashboard/director" /></MemoryRouter>)
    expect(screen.queryByRole('link', { name: /Panel institucional/ })).not.toBeInTheDocument()
    permit = true
  })
})

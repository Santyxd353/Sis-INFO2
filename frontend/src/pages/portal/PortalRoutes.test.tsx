import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Outlet } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
let role = 'Tutor', allowed = true
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, nombre: 'María', rol: { nombre: role }, alcance: { tipo: role === 'Director' ? 'COLEGIO' : 'PERSONAL', colegio_id: 1, unidad_id: 2 } }, loading: false, permisosCargando: false, can: (model: string) => allowed && model === 'portal-panel', hasRole: () => true, isSuperAdmin: () => role === 'SuperAdmin', logout: vi.fn() }) }))
vi.mock('../dashboard/FunctionalDashboardLayout', () => ({ default: () => <Outlet /> }))
vi.mock('../dashboard/PortalRolLayout', () => ({ default: () => <Outlet /> }))
vi.mock('../portal/PortalFamiliar', () => ({ default: () => <p>Contenido del portal familiar</p> }))
vi.mock('../portal/PanelInstitucional', () => ({ default: () => <p>Indicadores institucionales</p> }))
function open(path: string) { return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>) }
beforeEach(() => { role = 'Tutor'; allowed = true })
describe('rutas privadas HU29', () => {
  it.each(['Tutor', 'Estudiante'])('abre el portal familiar para %s', async perfil => { role = perfil; open('/dashboard/portal-familiar'); expect(await screen.findByText('Contenido del portal familiar')).toBeInTheDocument() })
  it.each(['/dashboard/tutor', '/dashboard/estudiante'])('integra el portal real en el inicio %s', async path => { role = path.includes('estudiante') ? 'Estudiante' : 'Tutor'; open(path); expect(await screen.findByText('Contenido del portal familiar')).toBeInTheDocument() })
  it.each(['Director', 'SuperAdmin', 'Secretaria'])('deniega el portal familiar a %s', async perfil => { role = perfil; open('/dashboard/portal-familiar'); expect(await screen.findByText('Acceso no disponible')).toBeInTheDocument(); expect(screen.queryByText('Contenido del portal familiar')).not.toBeInTheDocument() })
  it('abre el panel de director con permiso', async () => { role = 'Director'; open('/dashboard/panel-institucional'); expect(await screen.findByText('Indicadores institucionales')).toBeInTheDocument() })
  it('deniega el panel de director sin permiso', async () => { role = 'Director'; allowed = false; open('/dashboard/panel-institucional'); expect(await screen.findByText('Acceso no disponible')).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' })) })
  it.each(['Tutor', 'Estudiante', 'Secretaria', 'SuperAdmin'])('deniega el panel institucional a %s', async perfil => { role = perfil; open('/dashboard/panel-institucional'); expect(await screen.findByText('Acceso no disponible')).toBeInTheDocument() })
})

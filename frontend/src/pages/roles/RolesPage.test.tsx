import axios from 'axios'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RolesPage from './RolesPage'
import {
  listarAcciones, listarModelosPermitidos, listarRolesGestion, obtenerComponentesRol,
  obtenerConfiguracionInstitucional, obtenerPermisosRol,
} from '../../api/roles'

let profile: 'global' | 'director' = 'global'

vi.mock('../../app/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { perfil: profile === 'director' ? { puesto: { nombre: 'Director' } } : undefined, alcance: profile === 'global'
      ? { tipo: 'GLOBAL', colegio_id: null }
      : { tipo: 'COLEGIO', colegio_id: 1 } },
    isSuperAdmin: () => profile === 'global',
    can: () => true,
  }),
}))

vi.mock('../../api/catalogosInstitucionales', () => ({
  listarColegiosCatalogo: vi.fn().mockResolvedValue([]),
  listarUsuariosCatalogo: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../api/roles', async () => {
  const actual = await vi.importActual<typeof import('../../api/roles')>('../../api/roles')
  return {
    ...actual,
    listarRolesGestion: vi.fn(),
    listarAcciones: vi.fn(),
    listarModelosPermitidos: vi.fn(),
    listarRolesAsignables: vi.fn().mockResolvedValue({ data: [] }),
    listarUsuariosCatalogo: vi.fn().mockResolvedValue({ data: [] }),
    obtenerPermisosRol: vi.fn(),
    obtenerComponentesRol: vi.fn().mockResolvedValue({ data: { componentes: [] } }),
    obtenerConfiguracionInstitucional: vi.fn(),
  }
})

const respuesta = <T,>(data: T) => ({ data, status: 200, statusText: 'OK', headers: {}, config: {} as never })
const roles = [
  { id: 1, nombre: 'Regente', descripcion: '', colegio_id: null, unidad_id: null, activo: true, categoria: 'BASE', alcance: 'SISTEMA', permisos: [], componentes: [] },
  { id: 2, nombre: 'Plantilla académica', descripcion: '', colegio_id: null, unidad_id: null, activo: true, categoria: 'FUNCIONAL', alcance: 'SISTEMA', permisos: [], componentes: [] },
  { id: 3, nombre: 'Coordinación', descripcion: '', colegio_id: 1, unidad_id: null, activo: true, categoria: 'FUNCIONAL', alcance: 'COLEGIO', permisos: [], componentes: [] },
] as never
const adminBase = { id: 4, nombre: 'Admin', descripcion: '', colegio_id: null, unidad_id: null, activo: true, categoria: 'BASE', alcance: 'SISTEMA', permisos: [], componentes: [] }

describe('gestión dinámica de roles', () => {
  beforeEach(() => {
    profile = 'global'
    vi.mocked(listarRolesGestion).mockResolvedValue(respuesta(roles))
    vi.mocked(listarAcciones).mockResolvedValue(respuesta([{ id: 1, nombre: 'listar' }, { id: 2, nombre: 'editar' }]))
    vi.mocked(listarModelosPermitidos).mockResolvedValue(respuesta([{ id: 1, nombre: 'curso' }]))
    vi.mocked(obtenerPermisosRol).mockResolvedValue(respuesta({ rol_id: 1, permisos: [], metadatos: [] }))
    vi.mocked(obtenerConfiguracionInstitucional).mockResolvedValue(respuesta({
      rol: { id: 8, nombre: 'Admin', descripcion: 'Secretaría', colegio_id: 1, unidad_id: null, activo: true, categoria: 'FUNCIONAL', alcance: 'COLEGIO', permisos: [{ modelo: 'asignacion-docente', accion: 'listar' }, { modelo: 'asignacion-docente', accion: 'editar' }], componentes: [] },
      permisos: [], metadatos: [], perfil_objetivo: { nombre: 'Secretaría' }, alcance: 'COLEGIO', unidad: null,
    }) as never)
    vi.mocked(obtenerComponentesRol).mockResolvedValue(respuesta({ rol_id: 8, componentes: [{ componente: 'modulo:asignaciones', visible: true, editable: false }] }))
  })

  it('separa roles base de plantillas funcionales', async () => {
    render(<RolesPage />)
    expect(await screen.findByText('Roles base del sistema')).toBeInTheDocument()
    expect(screen.getByText('Plantillas funcionales del sistema')).toBeInTheDocument()
    expect(screen.getByText('Regente')).toBeInTheDocument()
  })

  it('director no puede editar roles de sistema', async () => {
    profile = 'director'
    render(<RolesPage />)
    await screen.findByText('Plantilla académica')
    expect(screen.queryByLabelText('Editar rol Plantilla académica')).not.toBeInTheDocument()
    fireEvent.click(screen.getAllByText('Permisos')[0])
    await waitFor(() => expect(screen.queryByText('Guardar permisos')).not.toBeInTheDocument())
  })

  it('muestra estado de carga al abrir la matriz de permisos', async () => {
    vi.mocked(obtenerPermisosRol).mockImplementation(() => new Promise((resolve) => {
      window.setTimeout(() => resolve(respuesta({ rol_id: 3, permisos: [] })), 100)
    }))
    render(<RolesPage />)
    await screen.findByText('Coordinación')
    fireEvent.click(screen.getAllByText('Permisos')[2])
    expect(await screen.findByText('Cargando permisos...')).toBeInTheDocument()
  })

  it('director cambia Admin base por el rol funcional de Secretaria al abrir Interfaz', async () => {
    profile = 'director'
    vi.spyOn(axios, 'get').mockResolvedValue({ data: [{ id: 2, nombre: 'Secretaria' }] } as never)
    vi.mocked(listarRolesGestion).mockResolvedValue(respuesta([...roles, adminBase] as never))
    render(<RolesPage />)
    const filaAdmin = (await screen.findByText('Admin')).closest('tr') as HTMLElement
    fireEvent.click(within(filaAdmin).getByText('Interfaz'))
    await waitFor(() => expect(obtenerConfiguracionInstitucional).toHaveBeenCalledWith({ puesto_id: expect.any(Number), unidad_id: null }))
    expect(obtenerComponentesRol).toHaveBeenCalledWith(8)
    expect(obtenerComponentesRol).not.toHaveBeenCalledWith(2)
    vi.restoreAllMocks()
  })
})

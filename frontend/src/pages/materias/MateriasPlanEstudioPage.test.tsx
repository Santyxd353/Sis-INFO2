import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MateriasPlanEstudioPage from './MateriasPlanEstudioPage'
import * as api from '../../api/materias'
import { listarUnidadesCatalogo } from '../../api/catalogosInstitucionales'

let scope: 'COLEGIO' | 'UNIDAD' = 'UNIDAD'
let permissions = new Set(['materia:listar', 'materia:crear', 'materia:editar', 'materia:desactivar', 'materia-curso:listar', 'materia-curso:crear', 'materia-curso:editar', 'materia-curso:desactivar'])
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: { alcance: { tipo: scope, colegio_id: 1, colegio_nombre: 'Colegio', unidad_id: scope === 'UNIDAD' ? 2 : null, unidad_nombre: 'Primaria' } }, can: (modelo: string, accion: string) => permissions.has(`${modelo}:${accion}`) }) }))
vi.mock('../../api/catalogosInstitucionales', () => ({ listarUnidadesCatalogo: vi.fn() }))
vi.mock('../../api/catalogosPaginados', () => ({ cargarCatalogoPaginado: vi.fn() }))
vi.mock('../../api/materias', () => ({
  listarMaterias: vi.fn(), listarMateriasCurso: vi.fn(), crearMateria: vi.fn(), actualizarMateria: vi.fn(), desactivarMateria: vi.fn(), vincularMateriaCurso: vi.fn(), actualizarMateriaCurso: vi.fn(), desactivarMateriaCurso: vi.fn(),
  normalizarColeccion: (data: { results?: unknown[]; count?: number } | unknown[]) => Array.isArray(data) ? { results: data, count: data.length } : { results: data.results ?? [], count: data.count ?? data.results?.length ?? 0 },
}))

const pagina = <T,>(results: T[]) => ({
  data: { count: results.length, next: null, previous: null, results },
  status: 200, statusText: 'OK', headers: {}, config: {} as never,
})
describe('Materias y plan de estudio', () => {
  beforeEach(() => {
    scope = 'UNIDAD'; permissions = new Set(['materia:listar', 'materia:crear', 'materia:editar', 'materia:desactivar', 'materia-curso:listar', 'materia-curso:crear', 'materia-curso:editar', 'materia-curso:desactivar'])
    vi.mocked(api.listarMaterias).mockResolvedValue(pagina([{ id: 5, unidad_educativa: 2, unidad_nombre: 'Primaria', nombre: 'Matemática', estado: 'ACTIVO', created_at: null, updated_at: null, eliminado_at: null }]))
    vi.mocked(api.listarMateriasCurso).mockResolvedValue(pagina([]))
    vi.mocked(listarUnidadesCatalogo).mockResolvedValue([{ id: 3, nombre: 'Secundaria' }] as never)
  })
  it('Secretaría conserva su unidad fija y consulta resultados paginados del servidor', async () => {
    render(<MateriasPlanEstudioPage />)
    expect(await screen.findByText('Matemática')).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Unidad educativa' })).not.toBeInTheDocument()
    expect(api.listarMaterias).toHaveBeenCalledWith(expect.objectContaining({ unidad_educativa: 2, page_size: 20 }), expect.anything())
  })
  it('normaliza el nombre antes de crear y conserva el formulario al recibir un error del backend', async () => {
    vi.mocked(api.crearMateria).mockRejectedValueOnce({ response: { status: 400, data: { nombre: ['Ya existe una materia activa.'] } }, isAxiosError: true })
    render(<MateriasPlanEstudioPage />); await screen.findByText('Matemática')
    fireEvent.click(screen.getByText('Nueva materia')); fireEvent.change(screen.getByLabelText('Nombre de materia'), { target: { value: '  Física   aplicada ' } }); fireEvent.click(screen.getByText('Guardar'))
    await waitFor(() => expect(api.crearMateria).toHaveBeenCalledWith({ unidad_educativa: 2, nombre: 'Física aplicada' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
  it('sin permiso de listar no carga consultas administrativas', () => {
    permissions = new Set(); render(<MateriasPlanEstudioPage />)
    expect(screen.getByText('No tiene permisos para realizar esta acción.')).toBeInTheDocument()
    expect(api.listarMaterias).not.toHaveBeenCalled()
  })
  it('Director puede abrir Nueva materia antes y después de seleccionar una unidad', async () => {
    scope = 'COLEGIO'; render(<MateriasPlanEstudioPage />)
    await waitFor(() => expect(listarUnidadesCatalogo).toHaveBeenCalledWith(1, expect.anything()))
    fireEvent.click(screen.getByText('Nueva materia'))
    expect(screen.getByText('Seleccione una unidad educativa antes de guardar la materia.')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Cerrar formulario'))
    fireEvent.change(screen.getByLabelText('Unidad educativa'), { target: { value: '3' } })
    fireEvent.click(screen.getByText('Nueva materia'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.queryByText('Seleccione una unidad educativa antes de guardar la materia.')).not.toBeInTheDocument()
  })
})

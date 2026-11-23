import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FilterValueInput from './FilterValueInput'
import { listarUnidadesCatalogo } from '../../../api/catalogosInstitucionales'
import { listarCalendarios, listarCursos } from '../../../api/asignacionesDocentes'
import { cargarCatalogoPaginado } from '../../../api/catalogosPaginados'

vi.mock('../../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: { alcance: { tipo: 'COLEGIO', colegio_id: 1 } } }) }))
vi.mock('../../../api/catalogosInstitucionales', () => ({ listarUnidadesCatalogo: vi.fn() }))
vi.mock('../../../api/asignacionesDocentes', () => ({ listarCalendarios: vi.fn(), listarCursos: vi.fn() }))
vi.mock('../../../api/catalogosPaginados', () => ({ cargarCatalogoPaginado: vi.fn() }))

const filtro = (control: string) => ({ campo: control, tipo: 'entero', control, operadores: ['eq', 'in'] })

describe('catálogos de filtros', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(listarUnidadesCatalogo).mockResolvedValue([{ id: 1, nombre: 'Primaria' }, { id: 2, nombre: 'Secundaria' }] as never)
  })
  it('muestra nombres de unidad y entrega su ID', async () => {
    const cambio = vi.fn()
    render(<FilterValueInput filtro={filtro('unidad')} operador="eq" valor="" onChange={cambio} />)
    await screen.findByRole('option', { name: 'Primaria' })
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: '1' } })
    expect(cambio).toHaveBeenCalledWith('1')
  })
  it('cancela cursos al cambiar unidad y no acepta una respuesta obsoleta', async () => {
    let resolver: (v: never) => void = () => {}
    vi.mocked(listarCursos).mockImplementationOnce(() => new Promise((resolve) => { resolver = resolve }))
      .mockResolvedValueOnce([{ id: 22, nombre: 'Curso nuevo' }] as never)
    const cambio = vi.fn()
    render(<FilterValueInput filtro={filtro('curso')} operador="eq" valor="" onChange={cambio} />)
    await screen.findByRole('option', { name: 'Primaria' })
    fireEvent.change(screen.getByLabelText('Unidad educativa para filtro'), { target: { value: '1' } })
    await waitFor(() => expect(listarCursos).toHaveBeenCalledTimes(1))
    const signal = vi.mocked(listarCursos).mock.calls[0][1]!
    fireEvent.change(screen.getByLabelText('Unidad educativa para filtro'), { target: { value: '2' } })
    expect(signal.aborted).toBe(true)
    await screen.findByRole('option', { name: 'Curso nuevo' })
    await act(async () => resolver([{ id: 11, nombre: 'Curso antiguo' }] as never))
    expect(screen.getByRole('option', { name: 'Curso nuevo' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Curso antiguo' })).not.toBeInTheDocument()
    expect(cambio).toHaveBeenCalledWith('')
  })
  it('carga gestión antes de períodos', async () => {
    vi.mocked(listarCalendarios).mockResolvedValue([{ id: 4, año: 2026 }] as never)
    vi.mocked(cargarCatalogoPaginado).mockResolvedValue([{ id: 8, nombre: 'Primer trimestre' }] as never)
    const cambio = vi.fn()
    render(<FilterValueInput filtro={filtro('periodo')} operador="eq" valor="" onChange={cambio} />)
    await screen.findByRole('option', { name: 'Primaria' })
    fireEvent.change(screen.getByLabelText('Unidad educativa para filtro'), { target: { value: '1' } })
    await screen.findByRole('option', { name: '2026' })
    fireEvent.change(screen.getByLabelText('Gestión académica para filtro'), { target: { value: '4' } })
    await screen.findByRole('option', { name: 'Primer trimestre' })
    expect(cargarCatalogoPaginado).toHaveBeenCalledWith('/calendario/periodos/', { calendario: 4 }, expect.any(AbortSignal))
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: '8' } })
    expect(cambio).toHaveBeenCalledWith('8')
  })
  it('consulta materias por unidad y entrega el ID', async () => {
    vi.mocked(cargarCatalogoPaginado).mockResolvedValue([{ id: 9, nombre: 'Matemática' }] as never)
    const cambio = vi.fn()
    render(<FilterValueInput filtro={filtro('materia')} operador="eq" valor="" onChange={cambio} />)
    await screen.findByRole('option', { name: 'Primaria' })
    fireEvent.change(screen.getByLabelText('Unidad educativa para filtro'), { target: { value: '1' } })
    await screen.findByRole('option', { name: 'Matemática' })
    expect(cargarCatalogoPaginado).toHaveBeenCalledWith('/academico/materias/', { unidad_educativa: 1 }, expect.any(AbortSignal))
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: '9' } })
    expect(cambio).toHaveBeenCalledWith('9')
  })
  it('cancela períodos de la gestión anterior', async () => {
    vi.mocked(listarCalendarios).mockResolvedValue([{ id: 4, año: 2025 }, { id: 5, año: 2026 }] as never)
    let resolver: (v: never) => void = () => {}
    vi.mocked(cargarCatalogoPaginado).mockImplementationOnce(() => new Promise((resolve) => { resolver = resolve }))
      .mockResolvedValueOnce([{ id: 8, nombre: 'Período nuevo' }] as never)
    render(<FilterValueInput filtro={filtro('periodo')} operador="eq" valor="" onChange={() => {}} />)
    await screen.findByRole('option', { name: 'Primaria' })
    fireEvent.change(screen.getByLabelText('Unidad educativa para filtro'), { target: { value: '1' } })
    await screen.findByRole('option', { name: '2025' })
    fireEvent.change(screen.getByLabelText('Gestión académica para filtro'), { target: { value: '4' } })
    await waitFor(() => expect(cargarCatalogoPaginado).toHaveBeenCalledTimes(1))
    const signal = vi.mocked(cargarCatalogoPaginado).mock.calls[0][2]!
    fireEvent.change(screen.getByLabelText('Gestión académica para filtro'), { target: { value: '5' } })
    expect(signal.aborted).toBe(true)
    await screen.findByRole('option', { name: 'Período nuevo' })
    await act(async () => resolver([{ id: 7, nombre: 'Período antiguo' }] as never))
    expect(screen.queryByRole('option', { name: 'Período antiguo' })).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Período nuevo' })).toBeInTheDocument()
  })
})

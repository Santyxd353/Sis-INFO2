import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError } from 'axios'
import ReportesOperativosPanel from './ReportesOperativosPanel'
import * as api from '../../api/reportes'
import { listarUnidadesCatalogo } from '../../api/catalogosInstitucionales'

vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: { alcance: { tipo: 'COLEGIO', colegio_id: 1 } } }) }))
vi.mock('../../api/catalogosInstitucionales', () => ({ listarUnidadesCatalogo: vi.fn().mockResolvedValue([{ id: 7, nombre: 'Unidad Norte' }]) }))
vi.mock('../../api/reportes', () => ({ catalogoReportesOperativos: vi.fn(), definicionesReportesOperativos: vi.fn(), crearDefinicionReporteOperativo: vi.fn(), actualizarDefinicionReporteOperativo: vi.fn(), previsualizarReporteOperativo: vi.fn(), exportarReporteOperativo: vi.fn() }))
const respuesta = (data: unknown) => ({ data }) as never
const fuente = { codigo: 'ALUMNOS', nombre: 'Alumnos', columnas: [{ campo: 'nombre', etiqueta: 'Nombre', tipo: 'texto' }], predeterminadas: ['nombre'], filtros: [{ campo: 'unidad', tipo: 'entero', control: 'unidad', operadores: ['eq'] }, { campo: 'activo', tipo: 'booleano', operadores: ['eq'] }] }

describe('reportes operativos', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(listarUnidadesCatalogo).mockResolvedValue([{ id: 7, nombre: 'Unidad Norte' }] as never)
    vi.mocked(api.catalogoReportesOperativos).mockResolvedValue(respuesta({ results: [fuente] }))
    vi.mocked(api.definicionesReportesOperativos).mockResolvedValue(respuesta({ results: [{ id: 3, codigo_fuente: 'ALUMNOS' }] }))
    vi.mocked(api.actualizarDefinicionReporteOperativo).mockResolvedValue(respuesta({ id: 3 }))
    vi.mocked(api.previsualizarReporteOperativo).mockResolvedValue(respuesta({ cantidad: 0, columnas: [], filas: [], limite_alcanzado: false }))
    vi.mocked(api.exportarReporteOperativo).mockResolvedValue(respuesta(new Blob(['archivo'])))
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:prueba'), revokeObjectURL: vi.fn() }))
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })
  it('reutiliza la especificación con ID numérico para vista, CSV y PDF', async () => {
    render(<ReportesOperativosPanel />)
    await screen.findByText('Alumnos')
    expect(screen.getByLabelText('Valor')).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Filtro opcional'), { target: { value: 'unidad' } })
    await screen.findByRole('option', { name: 'Unidad Norte' })
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: '7' } })
    for (const boton of ['Vista previa', 'CSV', 'PDF']) {
      fireEvent.click(screen.getByRole('button', { name: boton }))
      await waitFor(() => expect(api.actualizarDefinicionReporteOperativo).toHaveBeenCalledTimes(['Vista previa', 'CSV', 'PDF'].indexOf(boton) + 1))
      await waitFor(() => expect(screen.getByRole('button', { name: boton })).toBeEnabled())
    }
    for (const llamada of vi.mocked(api.actualizarDefinicionReporteOperativo).mock.calls) expect(llamada[1]).toEqual({ columnas: ['nombre'], filtros: [{ campo: 'unidad', operador: 'eq', valor: 7 }], orden: [] })
    expect(api.exportarReporteOperativo).toHaveBeenCalledWith(3, 'CSV')
    expect(api.exportarReporteOperativo).toHaveBeenCalledWith(3, 'PDF')
  })
  it('muestra un error general y conserva el mensaje al editar el valor', async () => {
    vi.mocked(api.actualizarDefinicionReporteOperativo).mockRejectedValue(new AxiosError('error', '400', undefined, undefined, { status: 400, data: { detail: 'No fue posible generar el reporte.' }, headers: {}, statusText: 'Bad Request', config: {} as never }))
    render(<ReportesOperativosPanel />)
    await screen.findByText('Alumnos')
    fireEvent.change(screen.getByLabelText('Filtro opcional'), { target: { value: 'activo' } })
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: 'true' } })
    fireEvent.click(screen.getByText('Vista previa'))
    await screen.findByText('No fue posible generar el reporte.')
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: 'false' } })
    expect(screen.getByText('No fue posible generar el reporte.')).toBeInTheDocument()
  })
  it('muestra error de permisos cuando el catálogo responde 403', async () => {
    vi.mocked(api.catalogoReportesOperativos).mockRejectedValue(new AxiosError('error', '403', undefined, undefined, { status: 403, data: {}, headers: {}, statusText: 'Forbidden', config: {} as never }))
    render(<ReportesOperativosPanel />)
    expect(await screen.findByText('No tiene permiso para este reporte.')).toBeInTheDocument()
  })
  it('no envía un valor vacío y envía booleanos como booleanos', async () => {
    render(<ReportesOperativosPanel />)
    await screen.findByText('Alumnos')
    fireEvent.change(screen.getByLabelText('Filtro opcional'), { target: { value: 'activo' } })
    fireEvent.click(screen.getByText('Vista previa'))
    await screen.findByText('Complete el valor del filtro.')
    expect(api.actualizarDefinicionReporteOperativo).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: 'false' } })
    fireEvent.click(screen.getByText('Vista previa'))
    await waitFor(() => expect(api.actualizarDefinicionReporteOperativo).toHaveBeenCalled())
    expect(vi.mocked(api.actualizarDefinicionReporteOperativo).mock.calls[0][1].filtros).toEqual([{ campo: 'activo', operador: 'eq', valor: false }])
  })
})

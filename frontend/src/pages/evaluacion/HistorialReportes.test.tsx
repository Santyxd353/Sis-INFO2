import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import HistorialReportes from './HistorialReportes'
import { archivarEjecucion, descargarEjecucion, listarEjecuciones } from '../../api/reportes'

vi.mock('../../api/reportes', () => ({
  listarEjecuciones: vi.fn(), archivarEjecucion: vi.fn(), descargarEjecucion: vi.fn(), detalleEjecucion: vi.fn(),
}))

const item = { id: 'abc', nombre: 'Reporte prueba', fuente: 'ESTUDIANTES_INSCRITOS', tipo: 'OPERATIVO', formato: 'CSV', estado: 'COMPLETADO', unidad: null, unidad_id: null, ejecutor: 'Ana', iniciada_at: '2026-01-01T00:00:00Z', finalizada_at: null, tamano: 10, archivado_at: null }

describe('Historial de reportes', () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(listarEjecuciones).mockResolvedValue({ data: { count: 21, results: [item], next: null, previous: null } } as never) })
  it('pagina, filtra y permite descargar y archivar', async () => {
    vi.mocked(descargarEjecucion).mockResolvedValue(undefined)
    vi.mocked(archivarEjecucion).mockResolvedValue({} as never)
    render(<HistorialReportes version={0} puedeArchivar />)
    expect(await screen.findByText('Reporte prueba')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Formato'), { target: { value: 'CSV' } })
    await waitFor(() => expect(listarEjecuciones).toHaveBeenCalledWith(expect.objectContaining({ formato: 'CSV' })))
    fireEvent.click(screen.getByText('Descargar'))
    await waitFor(() => expect(descargarEjecucion).toHaveBeenCalledWith(item))
    fireEvent.click(screen.getByText('Archivar'))
    await waitFor(() => expect(archivarEjecucion).toHaveBeenCalledWith('abc'))
    fireEvent.click(screen.getByText('Siguiente'))
    await waitFor(() => expect(listarEjecuciones).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })))
  })
  it('actualiza al exportar y muestra vacío o error', async () => {
    vi.mocked(listarEjecuciones).mockResolvedValue({ data: { count: 0, results: [] } } as never)
    const { rerender } = render(<HistorialReportes version={0} puedeArchivar={false} />)
    expect(await screen.findByText('No hay reportes para estos filtros.')).toBeTruthy()
    vi.mocked(listarEjecuciones).mockRejectedValue(new Error('error'))
    rerender(<HistorialReportes version={1} puedeArchivar={false} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('No fue posible cargar el historial')
  })
  it('no ofrece descarga para ejecuciones fallidas', async () => {
    vi.mocked(listarEjecuciones).mockResolvedValue({ data: { count: 1, results: [{ ...item, estado: 'ERROR' }] } } as never)
    render(<HistorialReportes version={0} puedeArchivar={false} />)
    await screen.findByText('Reporte prueba')
    expect(screen.queryByText('Descargar')).toBeNull()
  })
})

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RespaldosPage from './RespaldosPage'

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))
vi.mock('../../api/axiosInstance', () => ({ default: mocks }))

describe('RespaldosPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockImplementation((url: string) => Promise.resolve({ data: url.includes('configuracion') ? { activo: false, hora: '02:00:00', zona_horaria: 'America/La_Paz', ultima_fecha_programada: null } : url.includes('estado-procesador') ? { estado: 'DISPONIBLE', ultima_actividad: new Date().toISOString() } : [] }))
    mocks.post.mockResolvedValue({ data: {} })
    mocks.put.mockImplementation((_url, data) => Promise.resolve({ data }))
  })
  it('muestra el historial y solicita un respaldo', async () => {
    render(<RespaldosPage />)
    expect(await screen.findByText('Aún no hay respaldos registrados.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Crear respaldo ahora/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar respaldo' }))
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith('/respaldos/'))
    expect(await screen.findByRole('status')).toHaveTextContent('Solicitud registrada')
  })
  it('guarda la programación elegida', async () => {
    render(<RespaldosPage />)
    const activar = await screen.findByLabelText('Activar respaldo diario')
    fireEvent.click(activar)
    fireEvent.change(screen.getByLabelText('Hora'), { target: { value: '03:30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar programación' }))
    await waitFor(() => expect(mocks.put).toHaveBeenCalledWith('/respaldos/configuracion/', expect.objectContaining({ activo: true, hora: '03:30' })))
  })
  it('explica cuando el servidor no tiene las rutas y no presenta un historial vacío falso', async () => {
    mocks.get.mockRejectedValue({ isAxiosError: true, response: { status: 404 } })
    render(<RespaldosPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('El servidor no reconoce el módulo de respaldos')
    expect(screen.queryByText('Aún no hay respaldos registrados.')).not.toBeInTheDocument()
  })
})

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'
import { authAxios } from '../api/axiosInstance'

vi.mock('../api/axiosInstance', () => ({
  default: { get: vi.fn() },
  authAxios: { get: vi.fn() },
}))

describe('Portada pública', () => {
  beforeEach(() => vi.resetAllMocks())

  it('muestra los planes de la API y conserva su identificación al registrarse', async () => {
    vi.mocked(authAxios.get).mockResolvedValue({ data: { count: 1, results: [{
      id: 42, nombre: 'Plan académico', descripcion: 'Para tu colegio', precio: '125.00',
      moneda: 'BOB', periodicidad_display: 'Mensual', limite_usuarios: 25,
      limite_unidades: 2, modulos_habilitados: ['estudiante'],
    }] } })
    render(<MemoryRouter><Dashboard /></MemoryRouter>)
    expect(await screen.findByRole('heading', { name: 'Plan académico' })).toBeInTheDocument()
    expect(screen.getByText('Hasta 25 usuarios')).toBeInTheDocument()
    expect(screen.getByText('Hasta 2 unidades educativas')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Elegir este plan/ })).toHaveAttribute('href', '/registro-institucional?plan=42')
    expect(authAxios.get).toHaveBeenCalledWith('/suscripciones/planes-publicos/')
  })

  it('ofrece reintentar cuando falla la consulta de planes', async () => {
    vi.mocked(authAxios.get).mockRejectedValueOnce(new Error('sin conexión')).mockResolvedValueOnce({ data: [] })
    render(<MemoryRouter><Dashboard /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: /Reintentar/ }))
    await waitFor(() => expect(authAxios.get).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('No hay planes disponibles en este momento.')).toBeInTheDocument()
  })
})

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import VozPanel from './VozPanel'
import * as api from '../../api/reportes'

vi.mock('../../api/reportes', () => ({ interpretarVoz: vi.fn(), ejecutarVoz: vi.fn() }))
const contexto = { unidad_educativa: 1, calendario_academico: 2 }
beforeEach(() => vi.clearAllMocks())
afterEach(() => vi.unstubAllGlobals())

class ReconocimientoSimulado {
  static ultima: ReconocimientoSimulado
  static available = vi.fn(async () => 'available')
  start = vi.fn()
  stop = vi.fn()
  continuous = false
  interimResults = false
  onresult: ((event: { results: Array<Array<{ transcript: string }>> }) => void) | null = null
  onerror: ((event: { error: string }) => void) | null = null
  onend: (() => void) | null = null
  constructor() { ReconocimientoSimulado.ultima = this }
}

it('exige consentimiento para el servicio del navegador', async () => {
  ReconocimientoSimulado.available.mockResolvedValueOnce('unavailable').mockResolvedValueOnce('unavailable')
  vi.stubGlobal('SpeechRecognition', ReconocimientoSimulado)
  render(<VozPanel contexto={contexto} onExportado={() => {}} />)
  const consentimiento = await screen.findByRole('checkbox', { name: /autorizo utilizar/i })
  expect(screen.getByRole('button', { name: 'Iniciar escucha' })).toBeDisabled()
  fireEvent.click(consentimiento)
  fireEvent.click(screen.getByRole('button', { name: 'Iniciar escucha' }))
  expect(ReconocimientoSimulado.ultima.start).toHaveBeenCalledOnce()
})

it('reconoce localmente, permite editar y detener', async () => {
  vi.stubGlobal('SpeechRecognition', ReconocimientoSimulado)
  render(<VozPanel contexto={contexto} onExportado={() => {}} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Iniciar escucha' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Iniciar escucha' }))
  await screen.findByText(/escuchando ahora/i)
  const reconocimiento = ReconocimientoSimulado.ultima
  expect(reconocimiento.start).toHaveBeenCalledOnce()
  expect(reconocimiento.continuous).toBe(true)
  expect(reconocimiento.interimResults).toBe(true)
  act(() => reconocimiento.onresult?.({ results: [[{ transcript: 'asistencia de tercero a' }]] }))
  expect(screen.getByLabelText('Solicitud')).toHaveValue('asistencia de tercero a')
  fireEvent.change(screen.getByLabelText('Solicitud'), { target: { value: 'rendimiento' } })
  expect(screen.getByLabelText('Solicitud')).toHaveValue('rendimiento')
  fireEvent.click(screen.getByRole('button', { name: /detener y enviar consulta/i }))
  expect(reconocimiento.stop).toHaveBeenCalled()
  vi.mocked(api.interpretarVoz).mockResolvedValueOnce({ data: { estado: 'NO_SOPORTADO' } } as never)
  act(() => reconocimiento.onend?.())
  await waitFor(() => expect(api.interpretarVoz).toHaveBeenCalledWith('rendimiento', contexto))
  expect(await screen.findByRole('status')).toHaveTextContent(/no entendí esa consulta/i)
})

it('detiene el reconocimiento al desmontar', async () => {
  vi.stubGlobal('SpeechRecognition', ReconocimientoSimulado)
  const { unmount } = render(<VozPanel contexto={contexto} onExportado={() => {}} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Iniciar escucha' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Iniciar escucha' }))
  await screen.findByText(/escuchando ahora/i)
  const reconocimiento = ReconocimientoSimulado.ultima
  unmount()
  expect(reconocimiento.stop).toHaveBeenCalledOnce()
})

it('indica cómo habilitar el permiso de micrófono si el navegador lo deniega', async () => {
  vi.stubGlobal('SpeechRecognition', ReconocimientoSimulado)
  render(<VozPanel contexto={contexto} onExportado={() => {}} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Iniciar escucha' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Iniciar escucha' }))
  const reconocimiento = ReconocimientoSimulado.ultima
  act(() => reconocimiento.onerror?.({ error: 'not-allowed' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/permisos del sitio.*Micrófono a Permitir/i)
  expect(screen.getByLabelText('Solicitud')).toBeEnabled()
})

it('muestra la transcripción en vivo y la interpreta al detener la voz', async () => {
  vi.stubGlobal('SpeechRecognition', ReconocimientoSimulado)
  vi.mocked(api.interpretarVoz).mockResolvedValueOnce({ data: { estado: 'NO_SOPORTADO' } } as never)
  render(<VozPanel contexto={contexto} onExportado={() => {}} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Iniciar escucha' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Iniciar escucha' }))
  const reconocimiento = ReconocimientoSimulado.ultima
  act(() => reconocimiento.onresult?.({ results: [[{ transcript: 'Dame los estudiantes inscritos en secundaria' }]] }))
  expect(screen.getByLabelText('Solicitud')).toHaveValue('Dame los estudiantes inscritos en secundaria')
  fireEvent.click(screen.getByRole('button', { name: /detener y enviar consulta/i }))
  act(() => reconocimiento.onend?.())
  await waitFor(() => expect(api.interpretarVoz).toHaveBeenCalledWith('Dame los estudiantes inscritos en secundaria', contexto))
  expect(await screen.findByRole('status')).toHaveTextContent(/no entendí esa consulta/i)
})

it('ofrece texto manual y requiere confirmación explícita', async () => {
  vi.mocked(api.interpretarVoz).mockResolvedValue({ data: { estado: 'LISTO', intencion: 'ASISTENCIA', formato: 'VISTA', colegio: 1, filtros: contexto, token_interpretacion: 'firmado' } } as never)
  let resolver!: (value: never) => void
  vi.mocked(api.ejecutarVoz).mockImplementation(() => new Promise(resolve => { resolver = resolve }))
  render(<VozPanel contexto={contexto} onExportado={() => {}} />)
  expect(await screen.findByText(/no admite reconocimiento de voz/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Iniciar escucha' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Solicitud'), { target: { value: 'Consulta la asistencia' } })
  fireEvent.click(screen.getByRole('button', { name: 'Interpretar' }))
  const confirmar = await screen.findByRole('button', { name: 'Confirmar y ejecutar' })
  expect(api.ejecutarVoz).not.toHaveBeenCalled()
  fireEvent.click(confirmar)
  fireEvent.click(confirmar)
  expect(api.ejecutarVoz).toHaveBeenCalledTimes(1)
  await act(async () => resolver({ data: { indicadores: { asistencia_total: 3 }, metadatos: { matricula_actual: { advertencia: 'Dato actual' } } } } as never))
  await screen.findByText('Vista previa analítica')
  expect(api.ejecutarVoz).toHaveBeenCalledTimes(1)
})

it('muestra los estudiantes devueltos por el backend', async () => {
  vi.mocked(api.interpretarVoz).mockResolvedValueOnce({ data: { estado: 'LISTO', intencion: 'ESTUDIANTES_INSCRITOS', formato: 'VISTA', filtros: contexto, token_interpretacion: 'firmado' } } as never)
  vi.mocked(api.ejecutarVoz).mockResolvedValueOnce({ data: { tipo: 'ESTUDIANTES_INSCRITOS', columnas: ['Estudiante', 'Curso'], filas: [['Ana Pérez', 'Primero A']], limite: 100, hay_mas: false } } as never)
  render(<VozPanel contexto={contexto} onExportado={() => {}} />)
  fireEvent.change(screen.getByLabelText('Solicitud'), { target: { value: 'Lista estudiantes inscritos' } })
  fireEvent.click(screen.getByRole('button', { name: 'Interpretar' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Confirmar y ejecutar' }))
  expect(await screen.findByRole('heading', { name: 'Estudiantes inscritos' })).toBeInTheDocument()
  expect(screen.getByText('Ana Pérez')).toBeInTheDocument()
  expect(screen.getByText('Primero A')).toBeInTheDocument()
})

it('indica los selectores faltantes y permite volver a interpretar', async () => {
  vi.mocked(api.interpretarVoz).mockResolvedValueOnce({ data: { estado: 'FALTAN_DATOS', faltantes: ['unidad_educativa'] } } as never)
  const { rerender } = render(<VozPanel contexto={{}} onExportado={() => {}} />)
  fireEvent.change(screen.getByLabelText('Solicitud'), { target: { value: 'Consulta la asistencia' } })
  fireEvent.click(screen.getByRole('button', { name: 'Interpretar' }))
  expect(await screen.findByRole('status')).toHaveTextContent('unidad_educativa')
  rerender(<VozPanel contexto={contexto} onExportado={() => {}} />)
  vi.mocked(api.interpretarVoz).mockResolvedValueOnce({ data: { estado: 'LISTO', intencion: 'ASISTENCIA', formato: 'VISTA', filtros: contexto, token_interpretacion: 'firmado' } } as never)
  fireEvent.click(screen.getByRole('button', { name: 'Interpretar' }))
  await screen.findByRole('button', { name: 'Confirmar y ejecutar' })
  await waitFor(() => expect(api.interpretarVoz).toHaveBeenLastCalledWith('Consulta la asistencia', contexto))
})

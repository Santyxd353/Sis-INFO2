import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import AnaliticaPanel from './AnaliticaPanel'
import * as api from '../../api/reportes'

vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: { alcance: { tipo: 'COLEGIO', colegio_id: 1 } } }) }))
vi.mock('../../api/catalogosInstitucionales', () => ({ listarUnidadesCatalogo: vi.fn(async () => [{ id: 1, nombre: 'Unidad A' }, { id: 2, nombre: 'Unidad B' }]) }))
vi.mock('../../api/asignacionesDocentes', () => ({ listarCalendarios: vi.fn(async () => [{ id: 3, año: 2026 }]), listarCursos: vi.fn(async () => [{ id: 4, nombre: 'Curso A' }]), listarMateriasCurso: vi.fn(async () => []) }))
vi.mock('../../api/reportes', () => ({ resumenAnalitica: vi.fn(), exportarAnalitica: vi.fn() }))
vi.mock('../../api/axiosInstance', () => ({ default: { get: vi.fn(async () => ({ data: [] })) } }))

const resultado = { contexto: {}, indicadores: { matricula_actual: 4, promedio_general: null, porcentaje_aprobacion: null, porcentaje_asistencia: null, incidentes_total: 0 }, series: { matricula_por_curso: [{ etiqueta: 'Curso A', valor: 4 }] }, metadatos: { matricula_actual: { tipo_temporal: 'ACTUAL', advertencia: 'Fotografía actual', filtros_aplicados: [], filtros_no_aplicables: [] }, incidentes: { advertencia: 'Por fecha', filtros_no_aplicables: [] }, metricas_omitidas: [] } }

beforeEach(() => { vi.clearAllMocks(); vi.mocked(api.resumenAnalitica).mockResolvedValue({ data: resultado } as never) })

it('aplica filtros, muestra dato actual y limpia dependencias', async () => {
  render(<AnaliticaPanel onExportado={() => {}} />)
  await screen.findByRole('option', { name: 'Unidad A' })
  fireEvent.change(screen.getByLabelText('Unidad educativa'), { target: { value: '1' } })
  await screen.findByRole('option', { name: '2026' })
  fireEvent.change(screen.getByLabelText('Gestión'), { target: { value: '3' } })
  fireEvent.click(screen.getByRole('button', { name: 'Aplicar / actualizar' }))
  await screen.findByText('Fotografía actual')
  expect(api.resumenAnalitica).toHaveBeenCalledWith({ unidad_educativa: 1, calendario_academico: 3 }, expect.any(AbortSignal))
  expect(screen.getByText('Dato actual')).toBeInTheDocument()
  expect(screen.getAllByText('Sin datos').length).toBeGreaterThan(0)
  expect(screen.getByRole('table')).toHaveTextContent('Curso A')
  fireEvent.change(screen.getByLabelText('Unidad educativa'), { target: { value: '2' } })
  await waitFor(() => expect(screen.getByLabelText('Gestión')).toHaveValue(''))
  expect(screen.queryByText('Fotografía actual')).not.toBeInTheDocument()
})

it('muestra el error parcial solamente en la serie afectada', async () => {
  vi.mocked(api.resumenAnalitica).mockResolvedValue({ data: { ...resultado,
    series: { ...resultado.series, asistencia_por_fecha: null },
    metadatos: { ...resultado.metadatos, errores_parciales: [{ componente: 'asistencia_por_fecha', mensaje: 'No fue posible calcular esta serie.' }] },
  } } as never)
  render(<AnaliticaPanel onExportado={() => {}} />)
  await screen.findByRole('option', { name: 'Unidad A' })
  fireEvent.change(screen.getByLabelText('Unidad educativa'), { target: { value: '1' } })
  await screen.findByRole('option', { name: '2026' })
  fireEvent.change(screen.getByLabelText('Gestión'), { target: { value: '3' } })
  fireEvent.click(screen.getByRole('button', { name: 'Aplicar / actualizar' }))
  const alerta = await screen.findByRole('alert')
  expect(alerta).toHaveTextContent('No fue posible calcular esta serie.')
  expect(alerta.parentElement).toHaveTextContent('asistencia por fecha')
  expect(within(screen.getByRole('table')).getByText('Curso A')).toBeVisible()
  expect(screen.getByText('Matrícula actual').parentElement).toHaveTextContent('4')
})

it('descarta la respuesta anterior al cambiar de contexto', async () => {
  let resolverA!: (value: never) => void
  let resolverB!: (value: never) => void
  vi.mocked(api.resumenAnalitica).mockImplementationOnce(() => new Promise(resolve => { resolverA = resolve }))
    .mockImplementationOnce(() => new Promise(resolve => { resolverB = resolve }))
  render(<AnaliticaPanel onExportado={() => {}} />)
  await screen.findByRole('option', { name: 'Unidad A' })
  fireEvent.change(screen.getByLabelText('Unidad educativa'), { target: { value: '1' } })
  await screen.findByRole('option', { name: '2026' })
  fireEvent.change(screen.getByLabelText('Gestión'), { target: { value: '3' } })
  fireEvent.click(screen.getByRole('button', { name: 'Aplicar / actualizar' }))
  const signalA = vi.mocked(api.resumenAnalitica).mock.calls[0][1]!
  fireEvent.change(screen.getByLabelText('Unidad educativa'), { target: { value: '2' } })
  expect(signalA.aborted).toBe(true)
  await screen.findByRole('option', { name: '2026' })
  fireEvent.change(screen.getByLabelText('Gestión'), { target: { value: '3' } })
  fireEvent.click(screen.getByRole('button', { name: 'Aplicar / actualizar' }))
  await act(async () => resolverB({ data: { ...resultado, indicadores: { ...resultado.indicadores, matricula_actual: 9 } } } as never))
  expect(screen.getByText('Matrícula actual').parentElement).toHaveTextContent('9')
  await act(async () => resolverA({ data: resultado } as never))
  expect(screen.getByText('Matrícula actual').parentElement).toHaveTextContent('9')
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import api from '../../api/axiosInstance'
import HorariosPage from './HorariosPage'

const access = vi.hoisted(() => ({ write: true }))
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ can: (_model: string, action: string) => action === 'listar' || access.write }) }))
const mock = new MockAdapter(api)
const page = (results: unknown[], count = results.length) => ({ count, results, next: null, previous: null })
const assignment = { id: 8, nombre: 'Ana Pérez · Matemática · Primero A · 2026', profesor: 3, curso: 4, unidad_educativa: 2, colegio: 1, gestion: 2026, fecha_inicio: '2026-01-01', fecha_fin: '2026-12-31' }
const row = { id: 7, asignacion_docente: 8, aula: 9, colegio: 1, dia: 1, hora_inicio: '08:00:00', hora_fin: '09:00:00', fecha_inicio: '2026-01-01', fecha_fin: '2026-12-31', profesor: 3, curso: 4, unidad_educativa: 2, profesor_nombre: 'Ana Pérez', curso_nombre: 'Primero A', materia_nombre: 'Matemática', aula_nombre: 'Aula Norte', gestion: 2026, estado: 'ACTIVO' }
async function openCreate() {
  fireEvent.click(screen.getByRole('button', { name: 'Nuevo horario' }))
  await screen.findByRole('option', { name: assignment.nombre })
  fireEvent.change(screen.getByLabelText('Asignación docente *'), { target: { value: '8' } })
  await screen.findByRole('option', { name: 'Aula Norte' })
  fireEvent.change(screen.getByLabelText('Aula *'), { target: { value: '9' } })
  fireEvent.change(screen.getByLabelText('Hora de inicio *'), { target: { value: '10:00' } })
  fireEvent.change(screen.getByLabelText('Hora de fin *'), { target: { value: '11:00' } })
}
describe('HU12 horarios', () => {
  beforeEach(() => {
    access.write = true
    mock.onGet('/academico/horarios/').reply(200, page([row]))
    mock.onGet('/academico/horarios-asignaciones/').reply(200, page([assignment]))
    mock.onGet('/academico/horarios-aulas/').reply(200, page([{ id: 9, nombre: 'Aula Norte', colegio: 1 }]))
    mock.onGet('/academico/horarios-cursos/').reply(200, page([{ id: 4, nombre: 'Primero A' }]))
    mock.onGet('/academico/horarios-profesores/').reply(200, page([{ id: 3, nombre: 'Ana Pérez' }]))
  })
  afterEach(() => mock.reset())

  it('agrupa la semana por día y aplica filtros de curso, profesor y gestión en servidor', async () => {
    render(<HorariosPage />)
    expect(await screen.findByText('Matemática')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: /Lunes/ })).getByText('08:00 – 09:00')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Semana'), { target: { value: '2026-10-14' } })
    await screen.findByRole('option', { name: 'Primero A' })
    fireEvent.change(screen.getByLabelText('Curso'), { target: { value: '4' } })
    fireEvent.change(screen.getByLabelText('Profesor'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Gestión'), { target: { value: '2026' } })
    await waitFor(() => expect(mock.history.get.filter(c => c.url === '/academico/horarios/').at(-1)?.params).toMatchObject({ curso: '4', profesor: '3', gestion: '2026', semana: '2026-10-12', page: 1 }))
    fireEvent.click(screen.getByRole('button', { name: 'Semana siguiente' }))
    await waitFor(() => expect(mock.history.get.filter(c => c.url === '/academico/horarios/').at(-1)?.params.semana).toBe('2026-10-19'))
  })

  it('crea un horario con aula de la unidad de la asignación y sin estado ni profesor manipulable', async () => {
    mock.onPost('/academico/horarios/').reply(201, row)
    render(<HorariosPage />)
    await openCreate()
    fireEvent.click(screen.getByRole('button', { name: 'Guardar horario' }))
    expect(await screen.findByText('Horario creado.')).toBeInTheDocument()
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ asignacion_docente: 8, aula: 9, dia: 1, hora_inicio: '10:00', hora_fin: '11:00', fecha_inicio: '2026-01-01', fecha_fin: '2026-12-31' })
    expect(mock.history.get.find(c => c.url === '/academico/horarios-aulas/')?.params.asignacion_docente).toBe(8)
  })

  it('edita un horario y conserva la selección de asignación existente', async () => {
    mock.onPatch('/academico/horarios/7/').reply(200, row)
    render(<HorariosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Editar horario 7' }))
    expect(screen.getByLabelText('Asignación docente *')).toHaveValue('8')
    fireEvent.change(screen.getByLabelText('Hora de fin *'), { target: { value: '09:30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar horario' }))
    expect(await screen.findByText('Horario actualizado.')).toBeInTheDocument()
    expect(JSON.parse(mock.history.patch[0].data)).toMatchObject({ asignacion_docente: 8, aula: 9, hora_fin: '09:30' })
  })

  it('conserva segundos existentes al editar únicamente las fechas', async () => {
    mock.onGet('/academico/horarios/').reply(200, page([{ ...row, hora_inicio: '08:00:30', hora_fin: '09:00:45' }]))
    mock.onPatch('/academico/horarios/7/').reply(200, row)
    render(<HorariosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Editar horario 7' }))
    fireEvent.change(screen.getByLabelText('Vigente hasta *'), { target: { value: '2026-11-30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar horario' }))
    expect(await screen.findByText('Horario actualizado.')).toBeInTheDocument()
    expect(JSON.parse(mock.history.patch[0].data)).toMatchObject({ hora_inicio: '08:00:30', hora_fin: '09:00:45', fecha_fin: '2026-11-30' })
  })

  it('permite completar fecha final requerida de un horario histórico sin fecha final', async () => {
    mock.onGet('/academico/horarios/').reply(200, page([{ ...row, fecha_fin: null }]))
    mock.onPatch('/academico/horarios/7/').reply(200, row)
    render(<HorariosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Editar horario 7' }))
    expect(screen.getByLabelText('Vigente hasta *')).toHaveValue('')
    fireEvent.change(screen.getByLabelText('Vigente hasta *'), { target: { value: '2026-12-31' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar horario' }))
    expect(await screen.findByText('Horario actualizado.')).toBeInTheDocument()
    expect(JSON.parse(mock.history.patch[0].data).fecha_fin).toBe('2026-12-31')
  })

  it('exige confirmación antes de eliminar y actualiza la lista', async () => {
    mock.onDelete('/academico/horarios/7/').reply(() => {
      mock.onGet('/academico/horarios/').reply(200, page([]))
      return [204]
    })
    render(<HorariosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Eliminar horario 7' }))
    expect(mock.history.delete).toHaveLength(0)
    const dialog = screen.getByRole('dialog', { name: 'Eliminar horario' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirmar eliminación' }))
    expect(await screen.findByText('Horario eliminado.')).toBeInTheDocument()
    expect(await screen.findByText('Sin registros para esta consulta.')).toBeInTheDocument()
  })

  it('permite consultar al profesor sin acciones de escritura', async () => {
    access.write = false
    render(<HorariosPage />)
    expect(await screen.findByText('Matemática')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Nuevo horario' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Editar horario|Eliminar horario/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Solo lectura/)).toBeInTheDocument()
  })

  it('muestra el conflicto 409 y conserva el formulario para corregir', async () => {
    mock.onPost('/academico/horarios/').reply(409, { detail: 'El aula ya está ocupada en ese intervalo.' })
    render(<HorariosPage />)
    await openCreate()
    fireEvent.click(screen.getByRole('button', { name: 'Guardar horario' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('El aula ya está ocupada')
    expect(screen.getByLabelText('Hora de inicio *')).toHaveValue('10:00')
    expect(screen.getByRole('button', { name: 'Guardar horario' })).toBeEnabled()
  })

  it('bloquea acciones tras 403 sin cerrar el formulario', async () => {
    mock.onPost('/academico/horarios/').reply(403, { detail: 'No tiene permiso para crear horarios.' })
    render(<HorariosPage />)
    await openCreate()
    fireEvent.click(screen.getByRole('button', { name: 'Guardar horario' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No tiene permiso')
    expect(screen.getByRole('button', { name: 'Guardar horario' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeEnabled()
  })

  it('muestra carga y evita duplicar el guardado mientras espera', async () => {
    let finish!: (value: [number, unknown]) => void
    mock.onPost('/academico/horarios/').reply(() => new Promise(resolve => { finish = resolve }))
    render(<HorariosPage />)
    expect(screen.getByText('Cargando...')).toBeInTheDocument()
    await openCreate()
    const button = screen.getByRole('button', { name: 'Guardar horario' })
    fireEvent.click(button)
    fireEvent.click(button)
    await waitFor(() => expect(finish).toBeDefined())
    expect(screen.getByRole('button', { name: 'Guardando...' })).toBeDisabled()
    expect(mock.history.post).toHaveLength(1)
    await act(async () => finish([201, row]))
    expect(await screen.findByText('Horario creado.')).toBeInTheDocument()
  })

  it('conserva el formulario abierto mientras guarda sin permitir sustituirlo por otra operación', async () => {
    let finish!: (value: [number, unknown]) => void
    mock.onPost('/academico/horarios/').reply(() => new Promise(resolve => { finish = resolve }))
    render(<HorariosPage />)
    await openCreate()
    fireEvent.click(screen.getByRole('button', { name: 'Guardar horario' }))
    await waitFor(() => expect(finish).toBeDefined())
    expect(screen.getByRole('button', { name: 'Editar horario 7' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Eliminar horario 7' })).toBeDisabled()
    await act(async () => finish([201, row]))
    expect(await screen.findByText('Horario creado.')).toBeInTheDocument()
  })

  it('conserva selecciones entre páginas y reinicia búsqueda del catálogo en página uno', async () => {
    const second = { ...assignment, id: 22, nombre: 'Bruno · Física · Segundo B · 2026', colegio: 2 }
    mock.onGet('/academico/horarios-asignaciones/').reply(config => [200, page(config.params.search ? [second] : config.params.page === 2 ? [second] : [assignment], config.params.search ? 1 : 21)])
    mock.onGet('/academico/horarios-aulas/').reply(config => [200, page(config.params.asignacion_docente === 22 ? [{ id: 30, nombre: 'Aula Sur', colegio: 2, unidad_educativa: 3 }] : [{ id: 9, nombre: 'Aula Norte', colegio: 1, unidad_educativa: 2 }])])
    render(<HorariosPage />)
    await openCreate()
    fireEvent.click(within(screen.getByRole('group', { name: 'Páginas de asignación docente' })).getByRole('button', { name: 'Siguiente' }))
    await screen.findByRole('option', { name: second.nombre })
    expect(screen.getByLabelText('Asignación docente *')).toHaveValue('8')
    fireEvent.change(screen.getByLabelText('Asignación docente *'), { target: { value: '22' } })
    expect(screen.getByLabelText('Aula *')).toHaveValue('')
    await screen.findByRole('option', { name: 'Aula Sur' })
    expect(screen.queryByRole('option', { name: 'Aula Norte' })).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Buscar asignación docente'), { target: { value: 'Física' } })
    fireEvent.click(screen.getByRole('button', { name: 'Buscar opciones de asignación docente' }))
    await waitFor(() => expect(mock.history.get.filter(c => c.url === '/academico/horarios-asignaciones/').at(-1)?.params).toMatchObject({ page: 1, search: 'Física' }))
    expect(screen.getByLabelText('Asignación docente *')).toHaveValue('22')
  })

  it('mantiene el horario ante conflicto al eliminar y permite cancelar', async () => {
    mock.onDelete('/academico/horarios/7/').reply(409, { detail: 'El horario tiene sesiones de asistencia registradas.' })
    render(<HorariosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Eliminar horario 7' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar eliminación' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('sesiones de asistencia')
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Matemática')).toBeInTheDocument()
  })

  it('mantiene paginación visible para no ocultar horarios después de veinte', async () => {
    mock.onGet('/academico/horarios/').reply(config => [200, page(config.params.page === 2 ? [{ ...row, id: 22, materia_nombre: 'Física' }] : [row], 21)])
    render(<HorariosPage />)
    expect(await screen.findByText('Matemática')).toBeInTheDocument()
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Horarios paginados' })).getByRole('button', { name: 'Siguiente' }))
    expect(await screen.findByText('Física')).toBeInTheDocument()
    expect(screen.getByText('Página 2 · 21 registros')).toBeInTheDocument()
  })

  it('impide horas y fechas invertidas antes de enviar', async () => {
    render(<HorariosPage />)
    await openCreate()
    fireEvent.change(screen.getByLabelText('Hora de fin *'), { target: { value: '09:00' } })
    fireEvent.change(screen.getByLabelText('Vigente hasta *'), { target: { value: '2025-12-31' } })
    fireEvent.submit(screen.getByRole('form', { name: 'Formulario de horario' }))
    expect(await screen.findByText('La hora de fin debe ser posterior al inicio.')).toBeInTheDocument()
    expect(screen.getByText('La fecha final debe ser igual o posterior al inicio.')).toBeInTheDocument()
    expect(mock.history.post).toHaveLength(0)
  })

  it('ignora una respuesta anterior al cambiar de semana', async () => {
    let finish!: (value: [number, unknown]) => void
    let first = true
    mock.onGet('/academico/horarios/').reply(() => {
      if (first) { first = false; return new Promise(resolve => { finish = resolve }) }
      return [200, page([row])]
    })
    render(<HorariosPage />)
    await waitFor(() => expect(finish).toBeDefined())
    fireEvent.click(screen.getByRole('button', { name: 'Semana siguiente' }))
    expect(await screen.findByText('Matemática')).toBeInTheDocument()
    await act(async () => finish([200, page([{ ...row, materia_nombre: 'Respuesta antigua' }])]))
    expect(screen.queryByText('Respuesta antigua')).not.toBeInTheDocument()
    expect(screen.getByText('Matemática')).toBeInTheDocument()
  })

  it('muestra error de carga y permite reintentar', async () => {
    let first = true
    mock.onGet('/academico/horarios/').reply(() => {
      if (first) { first = false; return [500, { detail: 'Servicio no disponible.' }] }
      return [200, page([row])]
    })
    render(<HorariosPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Servicio no disponible.')
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Matemática')).toBeInTheDocument()
  })
})

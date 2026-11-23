import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import api from '../../api/axiosInstance'
import PortalFamiliar from './PortalFamiliar'
import PanelInstitucional from './PanelInstitucional'

let account = 1
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: account, rol: { nombre: 'Tutor' }, alcance: { colegio_id: 1, unidad_id: 2 } } }) }))
const mock = new MockAdapter(api)
const ana = { id: 8, nombre: 'Ana Rojas', curso: 'Primero A', unidad_educativa: 2, unidad_nombre: 'Unidad Central' }
const bruno = { ...ana, id: 9, nombre: 'Bruno Rojas' }
const gestion = { id: 3, anio: 2026, activo: true }, otraGestion = { id: 6, anio: 2025, activo: false }
const familia = {
  estudiantes: [ana, bruno], seleccionado: 8, estudiante: ana,
  gestiones: [gestion, otraGestion], gestion, periodos: [{ id: 4, nombre: 'Primer trimestre', estado: 'ABIERTO' }], periodo: null,
  notas: [{ materia: 'Matemática', periodos: [{ id: 4, nombre: 'Primer trimestre', nota: '78.00', condicion: 'APROBADO' }], anual: { nota: '78.00', condicion: 'APROBADO' } }],
  horarios: [{ id: 1, dia: 1, hora_inicio: '08:00:00', hora_fin: '08:45:00', materia: 'Matemática', docente: 'María Pérez', aula: 'Aula 1' }],
  asistencia: { fuente: 'SESIONES', total: 4, presentes: 3, faltas: 1, atrasos: 0, licencias: 0, porcentaje: 75, registros: [{ id: 2, fecha: '2026-11-16', estado: 'FALTA', materia: 'Matemática' }] },
  boletines: [{ id: 5, tipo: 'BOLETIN', periodo: 'Primer trimestre', version: 1, created_at: '2026-11-17T10:00:00Z', descarga_url: 'https://unsafe.example/private.pdf' }],
  comunicados: [{ id: 7, titulo: 'Reunión de familias', prioridad: 'NORMAL', leido_at: null, publicado_at: '2026-11-17T10:00:00Z' }],
  notificaciones: { no_leidas: 2, recientes: [{ id: 11, tipo: 'FALTA', titulo: 'Aviso de asistencia', created_at: '2026-11-17T10:00:00Z', leida_at: null, comunicado: null }] },
  pagos: { disponible: false, mensaje: 'Los pagos escolares todavía no están habilitados.' }, actualizado_at: '2026-11-17T10:00:00Z',
}
const panel = { unidades: [{ id: 2, nombre: 'Unidad Central' }], unidad_seleccionada: null, gestiones: [], gestion: null, periodos: [], periodo: null, indicadores: { estudiantes_activos: 12, docentes_activos: 4, cursos: 2, promedio: null, porcentaje_aprobacion: null, porcentaje_asistencia: null, comunicados_publicados: 3, porcentaje_lectura: 50 }, alcance: { colegio_id: 1, unidad_id: null }, actualizado_at: '2026-11-17T10:00:00Z' }
const show = (element: React.ReactNode) => render(<MemoryRouter>{element}</MemoryRouter>)
beforeEach(() => { account = 1; mock.onGet('/portal/familia/').reply(200, familia); mock.onGet('/portal/panel-director/').reply(200, panel) })
afterEach(() => { mock.reset(); vi.restoreAllMocks() })

describe('portal familiar', () => {
  it('presenta carga, datos reales, avisos, enlaces HU27 y pagos indisponibles', async () => {
    show(<PortalFamiliar />)
    expect(screen.getByRole('status')).toHaveTextContent('Cargando portal familiar')
    expect(await screen.findByRole('heading', { name: 'Ana Rojas' })).toBeInTheDocument()
    expect(screen.getAllByText('78.00').length).toBeGreaterThan(0)
    expect(screen.getByText('María Pérez')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Reunión de familias' })).toHaveAttribute('href', '/dashboard/comunicaciones?comunicado=7')
    expect(screen.getByRole('link', { name: /2 sin leer/ })).toHaveAttribute('href', '/dashboard/notificaciones')
    expect(screen.getByText(familia.pagos.mensaje)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Pagos no disponibles' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /pagar/i })).not.toBeInTheDocument()
  })
  it('mapea domingo al día siete del horario académico', async () => {
    mock.onGet('/portal/familia/').reply(200, { ...familia, horarios: [{ ...familia.horarios[0], dia: 7 }] })
    show(<PortalFamiliar />)
    expect(await screen.findByText('Domingo')).toBeInTheDocument()
  })
  it('borra datos al cambiar hijo, cancela la solicitud y reinicia gestión y periodo', async () => {
    show(<PortalFamiliar />)
    await screen.findByRole('heading', { name: 'Ana Rojas' })
    const firstSignal = mock.history.get[0].signal
    let finish!: (value: [number, unknown]) => void
    mock.onGet('/portal/familia/').reply(() => new Promise(resolve => { finish = resolve }))
    fireEvent.change(screen.getByLabelText('Estudiante'), { target: { value: '9' } })
    expect(screen.queryByText('María Pérez')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Ana Rojas' })).not.toBeInTheDocument()
    expect(firstSignal?.aborted).toBe(true)
    await waitFor(() => expect(mock.history.get).toHaveLength(2))
    expect(mock.history.get[1].params).toEqual({ estudiante: 9 })
    finish([200, { ...familia, estudiante: bruno, seleccionado: 9 }])
    expect(await screen.findByRole('heading', { name: 'Bruno Rojas' })).toBeInTheDocument()
  })
  it('filtra gestión y periodo, reiniciando el periodo al cambiar gestión', async () => {
    show(<PortalFamiliar />)
    await screen.findByRole('heading', { name: 'Ana Rojas' })
    mock.onGet('/portal/familia/').reply(200, { ...familia, periodo: 4 })
    fireEvent.change(screen.getByLabelText('Periodo académico'), { target: { value: '4' } })
    await waitFor(() => expect(mock.history.get[1].params).toEqual({ estudiante: 8, calendario_academico: 3, periodo: 4 }))
    await screen.findByRole('heading', { name: 'Ana Rojas' })
    mock.onGet('/portal/familia/').reply(200, { ...familia, gestion: otraGestion, periodo: null })
    fireEvent.change(screen.getByLabelText('Gestión académica'), { target: { value: '6' } })
    await waitFor(() => expect(mock.history.get[2].params).toEqual({ estudiante: 8, calendario_academico: 6 }))
  })
  it('elimina datos ante 404 ajeno y permite reintentar', async () => {
    show(<PortalFamiliar />)
    await screen.findByRole('heading', { name: 'Ana Rojas' })
    mock.onGet('/portal/familia/').reply(404, { detail: 'No encontrado.' })
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar portal' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se encontró información autorizada para esta selección.')
    expect(screen.queryByText('María Pérez')).not.toBeInTheDocument()
    mock.onGet('/portal/familia/').reply(200, familia)
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('heading', { name: 'Ana Rojas' })).toBeInTheDocument()
  })
  it('no conserva información ni filtros de la cuenta anterior y cancela al desmontar', async () => {
    const view = show(<PortalFamiliar />)
    await screen.findByRole('heading', { name: 'Ana Rojas' })
    const firstSignal = mock.history.get[0].signal
    mock.onGet('/portal/familia/').reply(200, { ...familia, estudiantes: [], estudiante: null, seleccionado: null, notas: [], horarios: [], boletines: [], comunicados: [] })
    account = 2
    view.rerender(<MemoryRouter><PortalFamiliar /></MemoryRouter>)
    expect(screen.queryByRole('heading', { name: 'Ana Rojas' })).not.toBeInTheDocument()
    expect(firstSignal?.aborted).toBe(true)
    expect(await screen.findByText('No hay estudiantes vinculados a esta cuenta.')).toBeInTheDocument()
    expect(mock.history.get[1].params).toEqual({})
    const lastSignal = mock.history.get[1].signal
    view.unmount()
    expect(lastSignal?.aborted).toBe(true)
  })
  it('ofrece descarga privada, usa blob temporal y libera el recurso', async () => {
    const create = vi.fn(() => 'blob:boletin'), revoke = vi.fn(), click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke }))
    mock.onGet('/estudiantes/documentos-academicos/5/descargar/').reply(200, new Blob(['%PDF']))
    show(<PortalFamiliar />)
    fireEvent.click(await screen.findByRole('button', { name: /Descargar boletín 5/ }))
    await waitFor(() => expect(click).toHaveBeenCalledOnce())
    expect(create).toHaveBeenCalledOnce()
    expect(revoke).toHaveBeenCalledWith('blob:boletin')
    expect(mock.history.get.at(-1)?.responseType).toBe('blob')
    expect(document.querySelector('a[href="https://unsafe.example/private.pdf"]')).toBeNull()
  })
  it('muestra fallo de descarga sin enlace público', async () => {
    mock.onGet('/estudiantes/documentos-academicos/5/descargar/').reply(403)
    show(<PortalFamiliar />)
    fireEvent.click(await screen.findByRole('button', { name: /Descargar boletín 5/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo descargar el boletín.')
  })
})

describe('panel institucional', () => {
  it('distingue contadores actuales y métricas filtradas sin inventar cero', async () => {
    show(<PanelInstitucional />)
    expect(await screen.findByText('Todo el colegio')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Situación actual' })).toBeInTheDocument()
    expect(within(screen.getByRole('article', { name: 'Estudiantes activos' })).getByText('12')).toBeInTheDocument()
    expect(within(screen.getByRole('article', { name: 'Promedio académico' })).getByText('Sin datos')).toBeInTheDocument()
    expect(screen.getByText('Seleccione una unidad y una gestión para consultar indicadores académicos.')).toBeInTheDocument()
  })
  it('envía unidad, gestión y periodo y limpia los indicadores durante la carga', async () => {
    show(<PanelInstitucional />)
    await screen.findByText('Todo el colegio')
    mock.onGet('/portal/panel-director/').reply(200, { ...panel, unidad_seleccionada: 2, gestiones: [gestion, otraGestion], gestion, periodos: familia.periodos })
    fireEvent.change(screen.getByLabelText('Unidad educativa'), { target: { value: '2' } })
    expect(screen.queryByRole('article', { name: 'Estudiantes activos' })).not.toBeInTheDocument()
    await screen.findByRole('article', { name: 'Estudiantes activos' })
    expect(mock.history.get[1].params).toEqual({ unidad_educativa: 2 })
    fireEvent.change(screen.getByLabelText('Periodo académico'), { target: { value: '4' } })
    await waitFor(() => expect(mock.history.get[2].params).toEqual({ unidad_educativa: 2, calendario_academico: 3, periodo: 4 }))
  })
  it('muestra un rechazo de acceso sin indicadores y ofrece reintento', async () => {
    mock.onGet('/portal/panel-director/').reply(403)
    show(<PanelInstitucional />)
    expect(await screen.findByRole('alert')).toHaveTextContent('No tiene permiso para consultar este portal.')
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
  })
})

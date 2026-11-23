import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import api from '../../api/axiosInstance'
import ComunicadosPage from './ComunicadosPage'
import NotificacionesPage from './NotificacionesPage'

let director = false
let permitted = true
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ can: (modelo: string, accion: string) => permitted && modelo === 'comunicacion' && accion === 'gestionar', user: { rol: { nombre: director ? 'Director' : 'Tutor' }, alcance: { tipo: director ? 'COLEGIO' : 'PERSONAL', colegio_id: 1, unidad_id: director ? null : 2 } } }) }))
const mock = new MockAdapter(api)
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results })
const comunicado = { id: 4, titulo: 'Reunión de familias', cuerpo: 'Mañana a las nueve', unidad_educativa: 2, curso: null, prioridad: 'NORMAL', requiere_confirmacion: true, estado: 'PUBLICADO', created_at: '2026-11-17T09:00:00Z', publicado_at: '2026-11-17T09:00:00Z', leido_at: null, puede_gestionar: false, es_destinatario: true, estadisticas: null }
const preferences = { COMUNICADO: true, FALTA: true, ATRASO: true, NOTA_BAJA: true, PAGO: true, CONTINGENCIA: true, CITACION: true, BOLETIN: true }
function renderPage(component: React.ReactNode) { return render(<MemoryRouter>{component}</MemoryRouter>) }
beforeEach(() => {
  director = false
  permitted = true
  mock.onGet('/comunicacion/comunicados/').reply(200, page([comunicado]))
  mock.onGet('/comunicacion/comunicados/4/').reply(200, comunicado)
  mock.onGet('/institucion/unidades-educativas/').reply(200, page([{ id: 2, nombre: 'Unidad Central', colegio: { id: 1 } }]))
  mock.onGet('/academico/cursos/').reply(200, page([{ id: 6, nombre: 'Primero A' }]))
  mock.onGet('/comunicacion/notificaciones/').reply(200, page([{ id: 8, tipo: 'FALTA', titulo: 'Aviso de asistencia', cuerpo: 'Consulte el registro', created_at: '2026-11-17T09:00:00Z', leida_at: null, comunicado: null, datos: {} }]))
  mock.onGet('/comunicacion/notificaciones/resumen/').reply(200, { no_leidas: 1 })
  mock.onGet('/comunicacion/preferencias/').reply(200, preferences)
})
afterEach(() => mock.reset())

describe('comunicados institucionales', () => {
  it('muestra carga y confirma lectura solamente con una acción explícita del destinatario', async () => {
    mock.onPost('/comunicacion/comunicados/4/leer/').reply(200, { ...comunicado, leido_at: '2026-11-17T10:00:00Z' })
    renderPage(<ComunicadosPage />)
    expect(screen.getByText('Cargando...')).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Reunión de familias' }))
    await screen.findByText('Mañana a las nueve')
    expect(mock.history.post).toHaveLength(0)
    expect(screen.queryByRole('button', { name: 'Nuevo comunicado' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Publicar' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar lectura' }))
    expect(await screen.findByText(/Lectura confirmada el/)).toBeInTheDocument()
    expect(mock.history.post).toHaveLength(1)
  })
  it('ofrece reintento y evita mostrar datos obsoletos tras un error', async () => {
    mock.onGet('/comunicacion/comunicados/').reply(500, { detail: 'Servicio temporalmente no disponible' })
    renderPage(<ComunicadosPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Servicio temporalmente no disponible')
    mock.onGet('/comunicacion/comunicados/').reply(200, page([comunicado]))
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('button', { name: 'Abrir Reunión de familias' })).toBeInTheDocument()
  })
  it('director destinatario confirma su lectura aunque también gestione el comunicado', async () => {
    director = true
    const institutional = { ...comunicado, puede_gestionar: true, es_destinatario: true }
    mock.onGet('/comunicacion/comunicados/4/').reply(200, institutional)
    mock.onPost('/comunicacion/comunicados/4/leer/').reply(200, { ...institutional, leido_at: '2026-11-17T10:00:00Z' })
    renderPage(<ComunicadosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Reunión de familias' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Confirmar lectura' }))
    expect(await screen.findByText(/Lectura confirmada el/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archivar' })).toBeInTheDocument()
    expect(mock.history.post.map(request => request.url)).toEqual(['/comunicacion/comunicados/4/leer/'])
  })
  it.each([
    { director: true, es_destinatario: false },
    { director: true, es_destinatario: undefined },
    { director: false, es_destinatario: false },
    { director: false, es_destinatario: undefined },
  ])('exige destinatario explícito del servidor: %j', async scenario => {
    director = scenario.director
    mock.onGet('/comunicacion/comunicados/4/').reply(200, { ...comunicado, curso: 6, puede_gestionar: scenario.director, es_destinatario: scenario.es_destinatario })
    renderPage(<ComunicadosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Reunión de familias' }))
    await screen.findByText('Mañana a las nueve')
    expect(screen.queryByRole('button', { name: 'Confirmar lectura' })).not.toBeInTheDocument()
    expect(mock.history.post).toHaveLength(0)
  })
  it('crea borrador con unidad y curso seleccionados sin publicar automáticamente', async () => {
    director = true
    mock.onPost('/comunicacion/comunicados/').reply(201, { ...comunicado, estado: 'BORRADOR', puede_gestionar: true })
    renderPage(<ComunicadosPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Nuevo comunicado' }))
    fireEvent.change(await screen.findByLabelText('Unidad educativa *'), { target: { value: '2' } })
    await screen.findByRole('option', { name: 'Primero A' })
    fireEvent.change(screen.getByLabelText('Curso destinatario'), { target: { value: '6' } })
    fireEvent.change(screen.getByLabelText('Título *'), { target: { value: 'Aviso nuevo' } })
    fireEvent.change(screen.getByLabelText('Contenido *'), { target: { value: 'Texto institucional' } })
    expect(screen.getByLabelText('Título *')).toHaveAttribute('maxlength', '200')
    expect(screen.getByLabelText('Contenido *')).toHaveAttribute('maxlength', '20000')
    fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }))
    await screen.findByText('Borrador guardado.')
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ titulo: 'Aviso nuevo', cuerpo: 'Texto institucional', unidad_educativa: 2, curso: 6, prioridad: 'NORMAL', requiere_confirmacion: true })
    expect(mock.history.post).toHaveLength(1)
  })
  it('gestor ve estadísticas y archivo pero no puede editar un publicado', async () => {
    director = true
    mock.onGet('/comunicacion/comunicados/4/').reply(200, { ...comunicado, puede_gestionar: true, estadisticas: { destinatarios: 10, leidos: 7, porcentaje_lectura: 70 } })
    renderPage(<ComunicadosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Reunión de familias' }))
    expect(await screen.findByText('7 de 10 destinatarios · 70% de lectura')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archivar' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Editar borrador' })).not.toBeInTheDocument()
  })
  it('edita un borrador existente usando PATCH y exige revisión antes de publicar', async () => {
    director = true
    mock.onGet('/comunicacion/comunicados/4/').reply(200, { ...comunicado, estado: 'BORRADOR', puede_gestionar: true })
    mock.onPatch('/comunicacion/comunicados/4/').reply(200, { ...comunicado, estado: 'BORRADOR', puede_gestionar: true })
    renderPage(<ComunicadosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Reunión de familias' }))
    await screen.findByRole('button', { name: 'Publicar' })
    expect(screen.queryByRole('button', { name: 'Archivar' })).not.toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Editar borrador' }))
    await screen.findByRole('option', { name: 'Primero A' })
    fireEvent.change(screen.getByLabelText('Título *'), { target: { value: 'Contenido revisado' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }))
    await screen.findByText('Borrador guardado.')
    expect(mock.history.patch[0].url).toBe('/comunicacion/comunicados/4/')
    expect(JSON.parse(mock.history.patch[0].data)).toMatchObject({ titulo: 'Contenido revisado', curso: null })
    expect(mock.history.post).toHaveLength(0)
  })
  it('publica tras confirmación y ofrece archivo conservando estadísticas', async () => {
    director = true
    mock.onGet('/comunicacion/comunicados/4/').reply(200, { ...comunicado, estado: 'BORRADOR', puede_gestionar: true })
    mock.onPost('/comunicacion/comunicados/4/publicar/').reply(200, { ...comunicado, puede_gestionar: true })
    mock.onPost('/comunicacion/comunicados/4/archivar/').reply(200, { ...comunicado, estado: 'ARCHIVADO', puede_gestionar: true, estadisticas: { destinatarios: 10, leidos: 7, porcentaje_lectura: 70 } })
    renderPage(<ComunicadosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Reunión de familias' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Publicar' }))
    expect(mock.history.post).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar publicación' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Editar borrador' })).not.toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Archivar' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar archivo' }))
    expect(await screen.findByText('7 de 10 destinatarios · 70% de lectura')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Archivar' })).not.toBeInTheDocument()
  })
  it('bloquea nuevas acciones tras un rechazo de autorización', async () => {
    director = true
    const draft = { ...comunicado, estado: 'BORRADOR', puede_gestionar: true }
    mock.onGet('/comunicacion/comunicados/4/').reply(200, draft)
    mock.onPost('/comunicacion/comunicados/4/publicar/').reply(403, { detail: 'Fuera de su ámbito' })
    renderPage(<ComunicadosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Reunión de familias' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Publicar' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar publicación' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Fuera de su ámbito')
    expect(screen.getByRole('button', { name: 'Confirmar publicación' })).toBeDisabled()
  })
  it('oculta creación, gestión y alertas cuando el permiso de dirección está revocado', async () => {
    director = true
    permitted = false
    mock.onGet('/comunicacion/comunicados/4/').reply(200, { ...comunicado, estado: 'BORRADOR', puede_gestionar: true })
    const view = renderPage(<ComunicadosPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Reunión de familias' }))
    await screen.findByText('Mañana a las nueve')
    expect(screen.queryByRole('button', { name: 'Nuevo comunicado' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Publicar' })).not.toBeInTheDocument()
    view.unmount()
    renderPage(<NotificacionesPage />)
    expect(screen.queryByRole('button', { name: 'Emitir alerta administrativa' })).not.toBeInTheDocument()
  })
})

describe('bandeja de notificaciones', () => {
  it('filtra categorías y no leídas, actualiza conteo y conserva aviso sin confirmar comunicado', async () => {
    mock.onPost('/comunicacion/notificaciones/8/leer/').reply(() => {
      mock.onGet('/comunicacion/notificaciones/resumen/').reply(200, { no_leidas: 0 })
      return [200, { id: 8 }]
    })
    renderPage(<NotificacionesPage />)
    await screen.findByText('1 sin leer')
    fireEvent.change(screen.getByLabelText('Categoría'), { target: { value: 'FALTA' } })
    fireEvent.click(screen.getByLabelText('Solo sin leer'))
    await waitFor(() => expect(mock.history.get.some(r => r.params?.tipo === 'FALTA' && r.params?.no_leidas === 'true')).toBe(true))
    fireEvent.click(await screen.findByRole('button', { name: 'Marcar como leída' }))
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    expect(mock.history.post[0].url).toBe('/comunicacion/notificaciones/8/leer/')
    expect(await screen.findByText('0 sin leer')).toBeInTheDocument()
  })
  it('explica preferencias y guarda cambios explícitos sin afectar la bandeja durable', async () => {
    mock.onPatch('/comunicacion/preferencias/').reply(200, { ...preferences, FALTA: false })
    renderPage(<NotificacionesPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Preferencias de avisos' }))
    await screen.findByText(/Los avisos permanecen en la bandeja/)
    fireEvent.click(await screen.findByLabelText('Faltas'))
    fireEvent.click(screen.getByRole('button', { name: 'Guardar preferencias' }))
    expect(await screen.findByText('Preferencias guardadas.')).toBeInTheDocument()
    expect(JSON.parse(mock.history.patch[0].data)).toMatchObject({ FALTA: false })
    mock.onGet('/comunicacion/preferencias/').reply(200, { ...preferences, FALTA: false })
    fireEvent.click(screen.getByRole('button', { name: 'Preferencias de avisos' }))
    fireEvent.click(screen.getByRole('button', { name: 'Preferencias de avisos' }))
    await waitFor(() => expect(mock.history.get.filter(r => r.url === '/comunicacion/preferencias/')).toHaveLength(2))
    expect(await screen.findByLabelText('Faltas')).not.toBeChecked()
  })
  it('conserva cambios pendientes de preferencias mientras se actualiza la bandeja', async () => {
    mock.onPost('/comunicacion/notificaciones/8/leer/').reply(200, { id: 8 })
    renderPage(<NotificacionesPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Preferencias de avisos' }))
    fireEvent.click(await screen.findByLabelText('Faltas'))
    expect(screen.getByLabelText('Faltas')).not.toBeChecked()
    fireEvent.click(await screen.findByRole('button', { name: 'Marcar como leída' }))
    await waitFor(() => expect(mock.history.get.filter(r => r.url === '/comunicacion/notificaciones/')).toHaveLength(2))
    expect(await screen.findByLabelText('Faltas')).not.toBeChecked()
  })
  it('no muestra emisión de alertas a familias', async () => {
    renderPage(<NotificacionesPage />)
    await screen.findByText('Aviso de asistencia')
    expect(screen.queryByRole('button', { name: 'Emitir alerta administrativa' })).not.toBeInTheDocument()
  })
  it('muestra bandeja vacía y permite reintentar errores en preferencias', async () => {
    mock.onGet('/comunicacion/notificaciones/').reply(200, page([]))
    mock.onGet('/comunicacion/preferencias/').reply(503, { detail: 'Preferencias no disponibles' })
    renderPage(<NotificacionesPage />)
    expect(await screen.findByText('Sin registros para esta consulta.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Preferencias de avisos' }))
    expect(await screen.findByText('Preferencias no disponibles')).toBeInTheDocument()
    mock.onGet('/comunicacion/preferencias/').reply(200, preferences)
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar preferencias' }))
    expect(await screen.findByRole('button', { name: 'Guardar preferencias' })).toBeInTheDocument()
  })
  it('director emite solo para estudiante de la unidad seleccionada y conserva la referencia al reintentar', async () => {
    director = true
    mock.onGet('/estudiantes/estudiantes/').reply(200, page([
      { id: 3, unidad: 2, usuario: { nombre: 'Ana', apellido: 'Rojas' } },
      { id: 9, unidad: { id: 8 }, usuario: { nombre: 'Otra', apellido: 'Unidad' } },
    ]))
    mock.onPost('/comunicacion/alertas/').reply(500, { detail: 'Reintente con la misma referencia' })
    renderPage(<NotificacionesPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Emitir alerta administrativa' }))
    fireEvent.change(await screen.findByLabelText('Unidad educativa *'), { target: { value: '2' } })
    expect(await screen.findByRole('option', { name: 'Ana Rojas' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Otra Unidad' })).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Estudiante *'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Tipo de alerta'), { target: { value: 'CONTINGENCIA' } })
    fireEvent.change(screen.getByLabelText('Título de alerta *'), { target: { value: 'Cambio de salida' } })
    fireEvent.change(screen.getByLabelText('Mensaje de alerta *'), { target: { value: 'Consulte a dirección' } })
    expect(screen.getByLabelText('Título de alerta *')).toHaveAttribute('maxlength', '200')
    expect(screen.getByLabelText('Mensaje de alerta *')).toHaveAttribute('maxlength', '20000')
    expect(screen.getByLabelText(/Referencia del evento/)).toHaveAttribute('maxlength', '120')
    fireEvent.click(screen.getByRole('button', { name: 'Enviar alerta' }))
    await screen.findByText('Reintente con la misma referencia')
    const payload = JSON.parse(mock.history.post[0].data)
    expect(payload).toMatchObject({ estudiante: 3, tipo: 'CONTINGENCIA', titulo: 'Cambio de salida', cuerpo: 'Consulte a dirección' })
    mock.onPost('/comunicacion/alertas/').reply(201, { creadas: 2 })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar alerta' }))
    expect(await screen.findByText('Alerta registrada: 2 avisos creados.')).toBeInTheDocument()
    expect(JSON.parse(mock.history.post[1].data).clave_evento).toBe(payload.clave_evento)
  })
})

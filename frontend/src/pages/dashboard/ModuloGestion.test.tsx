import MockAdapter from 'axios-mock-adapter'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from '../../api/axiosInstance'
import ModuloGestion from './ModuloGestion'
import { MODULOS } from './modules'

vi.mock('../../app/contexts/AuthContext', () => ({
  useAuth: () => ({ can: () => true, isSuperAdmin: () => true }),
}))

const mock = new MockAdapter(axios)
const endpointUsuarios = '/usuarios/usuarios/'
const endpointUnidades = '/institucion/unidades-educativas/'
const moduloUsuarios = MODULOS.find((modulo) => modulo.ruta.endsWith('/usuarios'))!
const roles = [
  { id: 1, nombre: 'Admin' },
  { id: 2, nombre: 'Profesor' },
  { id: 3, nombre: 'Tutor' },
  { id: 4, nombre: 'Estudiante' },
]
const puestos = [
  { id: 10, nombre: 'Director' },
  { id: 11, nombre: 'Secretaría' },
  { id: 12, nombre: 'Contador' },
  { id: 13, nombre: 'Tesorería' },
]
const colegios = [
  { id: 20, nombre: 'Colegio Central' },
  { id: 21, nombre: 'Colegio Norte' },
]
const unidades = [
  { id: 30, nombre: 'Primaria Central', colegio: { id: 20, nombre: 'Colegio Central' } },
  { id: 31, nombre: 'Secundaria Central', colegio: { id: 20, nombre: 'Colegio Central' } },
  { id: 40, nombre: 'Unidad Norte', colegio: { id: 21, nombre: 'Colegio Norte' } },
]

function prepararApi(usuarios: Record<string, unknown>[] = []) {
  mock.reset()
  mock.onGet(endpointUsuarios).reply(200, { count: usuarios.length, results: usuarios })
  mock.onGet('/usuarios/roles/').reply(200, { results: roles })
  mock.onGet('/usuarios/puestos/').reply(200, { results: puestos })
  mock.onGet('/institucion/colegios/').reply(200, { results: colegios })
  mock.onGet('/academico/cursos/').reply(200, { results: [{ id: 60, nombre: 'Curso 1' }] })
  mock.onGet(endpointUnidades).reply((config) => {
    const colegio = config.params?.colegio
    return [200, { results: colegio ? unidades.filter((unidad) => String(unidad.colegio.id) === String(colegio)) : unidades }]
  })
}

async function abrirFormulario() {
  render(<ModuloGestion modulo={moduloUsuarios} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Nuevo' }))
  await screen.findByRole('dialog')
}

function cambiarSelect(label: RegExp | string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function llenarDatosPersonales() {
  fireEvent.change(screen.getByLabelText(/Nombre\s+\*/), { target: { value: 'Ada' } })
  fireEvent.change(screen.getByLabelText(/Apellido\s+\*/), { target: { value: 'Lovelace' } })
  fireEvent.change(screen.getByLabelText(/CI\s+\*/), { target: { value: '123456' } })
  fireEvent.change(screen.getByLabelText(/Nombre de usuario/), { target: { value: 'ada' } })
  fireEvent.change(screen.getByLabelText(/Correo/), { target: { value: 'ada@example.test' } })
  fireEvent.change(screen.getByLabelText(/Contraseña/), { target: { value: 'secure-password' } })
  cambiarSelect(/Sexo/, 'F')
}

async function prepararSecretaria(colegioId = '20') {
  await abrirFormulario()
  cambiarSelect(/Rol/, '1')
  cambiarSelect(/Puesto administrativo/, '11')
  cambiarSelect(/Colegio/, colegioId)
  await screen.findByRole('option', { name: /Primaria Central/ })
}

async function prepararTesoreria(colegioId = '20') {
  await abrirFormulario()
  cambiarSelect(/Rol/, '1')
  cambiarSelect(/Puesto administrativo/, '13')
  cambiarSelect(/Colegio/, colegioId)
  await screen.findByRole('option', { name: /Primaria Central/ })
}

describe('asignación institucional de usuarios administrativos', () => {
  beforeEach(() => prepararApi())

  it('muestra Secretaria en lugar del rol genérico Admin cuando el puesto es de unidad', async () => {
    prepararApi([{
      id: 6, nombre: 'Maria', apellido: 'Secretaria', username: 'maria', email: 'maria@colegio.sec',
      rol: { id: 1, nombre: 'Admin' }, perfil: { tipo: 'admin', puesto: { id: 11, nombre: 'Secretaria' } },
      colegio: { id: 20, nombre: 'Colegio Central' }, unidad: { id: 30, nombre: 'Primaria Central' },
    }])
    render(<ModuloGestion modulo={moduloUsuarios} />)
    expect((await screen.findAllByText('Secretaria')).length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByText('Admin')).not.toBeInTheDocument()
  })

  it('no muestra puesto ni colegio administrativo a Profesor', async () => {
    await abrirFormulario()
    cambiarSelect(/Rol/, '2')
    expect(screen.queryByLabelText(/Puesto administrativo/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Colegio/)).not.toBeInTheDocument()
  })

  it('muestra Colegio para Admin con puesto Director', async () => {
    await abrirFormulario()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '10')
    expect(screen.getByLabelText(/Colegio/)).toBeInTheDocument()
  })

  it('oculta Unidad educativa o módulo para Director', async () => {
    await abrirFormulario()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '10')
    expect(screen.queryByLabelText(/Unidad educativa o módulo/)).not.toBeInTheDocument()
  })

  it('envía colegio_id al crear Director', async () => {
    mock.onPost(endpointUsuarios).reply(201, {})
    await abrirFormulario()
    llenarDatosPersonales()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '10')
    cambiarSelect(/Colegio/, '20')
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    expect(JSON.parse(mock.history.post[0].data)).toMatchObject({ colegio_id: 20 })
  })

  it('envía unidad_id null al crear Director', async () => {
    mock.onPost(endpointUsuarios).reply(201, {})
    await abrirFormulario()
    llenarDatosPersonales()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '10')
    cambiarSelect(/Colegio/, '20')
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    expect(JSON.parse(mock.history.post[0].data)).toHaveProperty('unidad_id', null)
  })

  it('no preselecciona automáticamente una unidad para Director', async () => {
    await abrirFormulario()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '10')
    cambiarSelect(/Colegio/, '20')
    expect(screen.queryByLabelText(/Unidad educativa o módulo/)).not.toBeInTheDocument()
    expect(mock.history.get.some((request) => request.params?.colegio === '20')).toBe(false)
  })

  it('muestra Colegio y Unidad educativa o módulo para Secretaría', async () => {
    await prepararSecretaria()
    expect(screen.getByLabelText(/Colegio/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Unidad educativa o módulo/)).toBeInTheDocument()
  })

  it('mantiene deshabilitada la unidad si no se ha seleccionado colegio', async () => {
    await abrirFormulario()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '11')
    expect(screen.getByLabelText(/Unidad educativa o módulo/)).toBeDisabled()
  })

  it('consulta unidades usando el colegio seleccionado', async () => {
    await prepararSecretaria('20')
    await waitFor(() => expect(mock.history.get.some(
      (request) => request.url === endpointUnidades && request.params?.colegio === '20',
    )).toBe(true))
  })

  it('muestra solo unidades del colegio seleccionado', async () => {
    await prepararSecretaria('20')
    const selector = screen.getByLabelText(/Unidad educativa o módulo/)
    expect(within(selector).getByRole('option', { name: /Primaria Central/ })).toBeInTheDocument()
    expect(within(selector).queryByRole('option', { name: /Unidad Norte/ })).not.toBeInTheDocument()
  })

  it('limpia unidad al cambiar de colegio', async () => {
    await prepararSecretaria('20')
    cambiarSelect(/Unidad educativa o módulo/, '30')
    cambiarSelect(/Colegio/, '21')
    expect(screen.getByLabelText(/Unidad educativa o módulo/)).toHaveValue('')
    await screen.findByRole('option', { name: /Unidad Norte/ })
  })

  it('valida que Secretaría seleccione unidad', async () => {
    await prepararSecretaria()
    const form = screen.getByRole('button', { name: 'Guardar' }).closest('form')
    expect(form).not.toBeNull()
    fireEvent.submit(form!)
    expect(await screen.findByText('Seleccione una unidad educativa o módulo.')).toBeInTheDocument()
    expect(mock.history.post).toHaveLength(0)
  })

  it('envía colegio_id y unidad_id para Secretaría', async () => {
    mock.onPost(endpointUsuarios).reply(201, {})
    await prepararSecretaria()
    llenarDatosPersonales()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '11')
    cambiarSelect(/Colegio/, '20')
    await screen.findByRole('option', { name: /Primaria Central/ })
    cambiarSelect(/Unidad educativa o módulo/, '30')
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    expect(JSON.parse(mock.history.post[0].data)).toMatchObject({ colegio_id: 20, unidad_id: 30 })
  })

  it('al cambiar de Secretaría a Director limpia y oculta la unidad', async () => {
    await prepararSecretaria()
    cambiarSelect(/Unidad educativa o módulo/, '30')
    cambiarSelect(/Puesto administrativo/, '10')
    expect(screen.queryByLabelText(/Unidad educativa o módulo/)).not.toBeInTheDocument()
    expect(screen.getByLabelText(/Colegio/)).toHaveValue('20')
  })

  it('al cambiar de Director a Secretaría requiere selección explícita', async () => {
    await abrirFormulario()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '10')
    cambiarSelect(/Colegio/, '20')
    cambiarSelect(/Puesto administrativo/, '11')
    expect(screen.getByLabelText(/Unidad educativa o módulo/)).toHaveValue('')
    expect(screen.getByLabelText(/Unidad educativa o módulo/)).toBeRequired()
  })

  it('precarga el colegio y omite unidad heredada al editar Director', async () => {
    prepararApi([{
      id: 5, nombre: 'Eva', apellido: 'Directora', ci: '5', username: 'eva',
      email: 'eva@example.test', rol: roles[0], puesto: puestos[0],
      colegio: colegios[0], unidad: unidades[0],
    }])
    render(<ModuloGestion modulo={moduloUsuarios} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Editar' }))
    expect(await screen.findByLabelText(/Colegio/)).toHaveValue('20')
    expect(screen.queryByLabelText(/Unidad educativa o módulo/)).not.toBeInTheDocument()
  })

  it('precarga colegio de alcance si no hay relación colegio directa al editar Director', async () => {
    prepararApi([{
      id: 5, nombre: 'Eva', apellido: 'Directora', ci: '5', username: 'eva',
      email: 'eva@example.test', rol: roles[0], puesto: puestos[0],
      alcance: { tipo: 'COLEGIO', colegio_id: 21, colegio_nombre: 'Colegio Norte', unidad_id: 40, unidad_nombre: 'Unidad Norte' },
    }])
    render(<ModuloGestion modulo={moduloUsuarios} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Editar' }))
    expect(await screen.findByLabelText(/Colegio/)).toHaveValue('21')
    expect(screen.queryByLabelText(/Unidad educativa o módulo/)).not.toBeInTheDocument()
  })

  it('precarga colegio y unidad solo después de cargar unidades de Secretaría', async () => {
    prepararApi([{
      id: 6, nombre: 'Sara', apellido: 'Secretaria', ci: '6', username: 'sara',
      email: 'sara@example.test', rol: roles[0], puesto: puestos[1],
      colegio: colegios[0], unidad: unidades[0],
    }])
    render(<ModuloGestion modulo={moduloUsuarios} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Editar' }))
    const unit = await screen.findByLabelText(/Unidad educativa o módulo/)
    await waitFor(() => expect(unit).toHaveValue('30'))
    expect(screen.getByLabelText(/Colegio/)).toHaveValue('20')
    expect(mock.history.get.some((request) => request.url === endpointUnidades
      && request.params?.colegio === '20')).toBe(true)
  })

  it('mantiene abierto el modal si la creación responde 400', async () => {
    mock.onPost(endpointUsuarios).reply(400, { colegio_id: ['Colegio requerido'] })
    await abrirFormulario()
    llenarDatosPersonales()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '10')
    cambiarSelect(/Colegio/, '20')
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('muestra errores backend en los campos institucionales correspondientes', async () => {
    mock.onPost(endpointUsuarios).reply(400, {
      colegio_id: ['El colegio está inactivo.'],
      unidad_id: ['La unidad no pertenece al colegio.'],
    })
    await prepararSecretaria()
    llenarDatosPersonales()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '11')
    cambiarSelect(/Colegio/, '20')
    await screen.findByRole('option', { name: /Primaria Central/ })
    cambiarSelect(/Unidad educativa o módulo/, '30')
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByText('El colegio está inactivo.')).toBeInTheDocument()
    expect(await screen.findByText('La unidad no pertenece al colegio.')).toBeInTheDocument()
  })

  it('muestra Todas las unidades para Director con colegio asignado', async () => {
    prepararApi([{
      id: 5, nombre: 'Eva', apellido: 'Directora', ci: '5', username: 'eva',
      email: 'eva@example.test', rol: roles[0], puesto: puestos[0], colegio: colegios[0],
      unidad: unidades[0],
    }])
    render(<ModuloGestion modulo={moduloUsuarios} />)
    expect(await screen.findByText('Todas las unidades')).toBeInTheDocument()
    expect(screen.getByText('Colegio Central')).toBeInTheDocument()
  })

  it('muestra la unidad concreta para Secretaría', async () => {
    prepararApi([{
      id: 6, nombre: 'Sara', apellido: 'Secretaria', ci: '6', username: 'sara',
      email: 'sara@example.test', rol: roles[0], puesto: puestos[1],
      colegio: colegios[0], unidad: unidades[0],
    }])
    render(<ModuloGestion modulo={moduloUsuarios} />)
    expect(await screen.findByText('Primaria Central')).toBeInTheDocument()
    expect(screen.getByText('Colegio Central')).toBeInTheDocument()
  })

  it('conserva el flujo de creación de Profesor con unidad y cursos', async () => {
    mock.onPost(endpointUsuarios).reply(201, {})
    await abrirFormulario()
    llenarDatosPersonales()
    cambiarSelect(/Rol/, '2')
    await screen.findByRole('option', { name: /Primaria Central/ })
    cambiarSelect(/Unidad educativa o módulo/, '30')
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    const payload = JSON.parse(mock.history.post[0].data)
    expect(payload).toMatchObject({ rol_id: 2, unidad_id: 30 })
    expect(payload).not.toHaveProperty('colegio_id')
    expect(payload).not.toHaveProperty('puesto_id')
  })

  it('limpia colegio, unidad y puesto al cambiar Admin a otro rol', async () => {
    await abrirFormulario()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '10')
    cambiarSelect(/Colegio/, '20')
    cambiarSelect(/Rol/, '2')
    expect(screen.queryByLabelText(/Puesto administrativo/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Colegio/)).not.toBeInTheDocument()
    expect(screen.getByLabelText(/Unidad educativa o módulo/)).toHaveValue('')
  })

  it('muestra el texto de ayuda de Director', async () => {
    await abrirFormulario()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '10')
    expect(screen.getByText('El Director tendrá acceso a todas las unidades educativas del colegio.')).toBeInTheDocument()
  })

  it('normaliza Secretaría con y sin tilde para determinar el puesto', async () => {
    prepararApi()
    mock.onGet('/usuarios/puestos/').reply(200, { results: [{ id: 11, nombre: 'Secretaria' }] })
    await abrirFormulario()
    cambiarSelect(/Rol/, '1')
    cambiarSelect(/Puesto administrativo/, '11')
    expect(screen.getByLabelText(/Colegio/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Unidad educativa o módulo/)).toBeInTheDocument()
  })

  it('permite Tesorería con todas las unidades y limita las opciones al colegio seleccionado', async () => {
    await prepararTesoreria()
    const unidad = screen.getByLabelText(/Unidad educativa o módulo/)
    expect(unidad).not.toBeRequired()
    expect(within(unidad).getByRole('option', { name: /Todas las unidades/ })).toHaveValue('')
    expect(within(unidad).getByRole('option', { name: /Primaria Central/ })).toBeInTheDocument()
    expect(within(unidad).queryByRole('option', { name: /Unidad Norte/ })).not.toBeInTheDocument()
    expect(mock.history.get.some((request) => request.url === endpointUnidades
      && request.params?.colegio === '20')).toBe(true)
  })

  it('crea Tesorería con alcance COLEGIO cuando se elige Todas las unidades', async () => {
    mock.onPost(endpointUsuarios).reply(201, {})
    await prepararTesoreria()
    llenarDatosPersonales()
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    expect(JSON.parse(mock.history.post[0].data)).toMatchObject({ rol_id: 1, puesto_id: 13, colegio_id: 20, unidad_id: null })
  })

  it('crea Tesorería con alcance UNIDAD cuando se selecciona una unidad autorizada', async () => {
    mock.onPost(endpointUsuarios).reply(201, {})
    await prepararTesoreria()
    llenarDatosPersonales()
    cambiarSelect(/Unidad educativa o módulo/, '30')
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    expect(JSON.parse(mock.history.post[0].data)).toMatchObject({ colegio_id: 20, unidad_id: 30 })
  })
})

import MockAdapter from 'axios-mock-adapter'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import axios from '../../api/axiosInstance'
import ModuloGestion from './ModuloGestion'
import { MODULOS } from './modules'

vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ can: () => true, isSuperAdmin: () => true }) }))
const api = new MockAdapter(axios)
const modulo = MODULOS.find(item => item.ruta.endsWith('/estructura-academica'))!
const grado = { id: 10, nombre: '2do', unidad_educativa: 1 }
const paralelo = { id: 5, letra: 'A', grado }
afterEach(() => api.reset())

function preparar() {
  api.onGet('/academico/grados/').reply(200, [])
  api.onGet('/academico/paralelos/').reply(200, [paralelo])
  api.onGet('/academico/cursos/').reply(200, [{ id: 5, nombre: 'Curso A', paralelo, tutor: null }])
  api.onGet('/institucion/unidades-educativas/').reply(200, [{ id: 1, nombre: 'Unidad A' }])
  api.onGet('/personal/profesores/').reply(200, [
    { id: 1, unidad_id: 1, usuario: { nombre: 'Docente', apellido: 'Local' } },
    { id: 2, unidad_id: 2, usuario: { nombre: 'Docente', apellido: 'Otra unidad' } },
  ])
}

it('ofrece docentes de la unidad del paralelo seleccionado', async () => {
  preparar()
  render(<ModuloGestion modulo={modulo} />)
  const fila = (await screen.findByText('Curso A')).closest('tr')!
  fireEvent.click(within(fila).getByTitle('Editar'))
  const tutor = await screen.findByLabelText('Docente tutor')
  await within(tutor).findByRole('option', { name: 'Docente · Local' })
  expect(within(tutor).queryByRole('option', { name: 'Docente · Otra unidad' })).not.toBeInTheDocument()
})

it('permite crear prekínder sin pedir número y conserva el contrato numérico', async () => {
  preparar()
  api.onPost('/academico/grados/').reply(201, {})
  render(<ModuloGestion modulo={modulo} />)
  const titulo = await screen.findByRole('heading', { name: 'Grados' })
  fireEvent.click(within(titulo.closest('section')!).getByRole('button', { name: 'Nuevo' }))
  await screen.findByRole('option', { name: 'Unidad A' })
  fireEvent.change(screen.getByLabelText(/Unidad educativa/), { target: { value: '1' } })
  fireEvent.change(screen.getByLabelText(/Nivel educativo/), { target: { value: 'INI' } })
  fireEvent.change(screen.getByLabelText(/Etapa de inicial/), { target: { value: '1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
  await waitFor(() => expect(api.history.post).toHaveLength(1))
  expect(JSON.parse(api.history.post[0].data)).toMatchObject({ unidad_educativa: 1, nivel_educativo: 'INI', numero: 1 })
})

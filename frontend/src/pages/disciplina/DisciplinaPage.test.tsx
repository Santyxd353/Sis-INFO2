import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import axios from '../../api/axiosInstance'
import DisciplinaPage from './DisciplinaPage'

vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ can: () => true, user: { id: 9 } }) }))
const mock = new MockAdapter(axios)
const page = (results: unknown[]) => ({ count: results.length, results, next: null, previous: null })
const incident = { id: 2, historial_inscripcion: 1, fecha: '2026-03-01T12:00:00Z', tipo: 'FALTA', severidad: 'LEVE', descripcion: 'Incidente inicial', estado: 'ABIERTO', created_by: 9, responsable_nombre: 'Regente', estudiante_nombre: 'Ana Test', curso_nombre: 'Tercero A' }
describe('HU14 disciplina', () => {
  beforeEach(() => {
    mock.onGet('/estudiantes/inscripciones-disciplina/').reply(200, page([{id:1, estudiante:4, estudiante_nombre:'Ana Test', curso_nombre:'Tercero A'}]))
    mock.onGet('/estudiantes/incidentes/').reply(200, page([incident]))
    mock.onGet('/estudiantes/tutores-disciplina/').reply(200, page([{id:3,nombre:'Tutor Test'}]))
    mock.onGet('/estudiantes/citaciones/').reply(200, page([]))
  })
  afterEach(() => mock.reset())
  it('consulta historial y crea observación con responsable del servidor', async () => {
    mock.onPost('/estudiantes/incidentes/').reply(201, incident)
    render(<DisciplinaPage />)
    fireEvent.change(await screen.findByLabelText('Inscripción'), {target:{value:'1'}})
    expect(await screen.findByText('Incidente inicial')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', {name:'Nueva observación'}))
    fireEvent.change(screen.getByLabelText('Descripción *'), {target:{value:'Observación nueva'}})
    fireEvent.click(screen.getByRole('button', {name:'Guardar observación'}))
    expect(await screen.findByText('Observación guardada.')).toBeInTheDocument()
    expect(JSON.parse(mock.history.post[0].data)).toMatchObject({historial_inscripcion:1,descripcion:'Observación nueva'})
    expect(JSON.parse(mock.history.post[0].data)).not.toHaveProperty('created_by')
  })
  it('genera citación vinculada al tutor', async () => {
    mock.onPost('/estudiantes/citaciones/').reply(201, {id:8})
    render(<DisciplinaPage />)
    fireEvent.change(await screen.findByLabelText('Inscripción'), {target:{value:'1'}})
    fireEvent.click(await screen.findByRole('button', {name:'Citaciones del incidente 2'}))
    fireEvent.click(await screen.findByRole('button', {name:'Nueva citación'}))
    fireEvent.change(await screen.findByLabelText('Tutor *'), {target:{value:'3'}})
    fireEvent.change(screen.getByLabelText('Fecha de citación *'), {target:{value:'2026-10-20T10:30'}})
    fireEvent.click(screen.getByRole('button', {name:'Guardar citación'}))
    expect(await screen.findByText('Citación guardada.')).toBeInTheDocument()
    expect(JSON.parse(mock.history.post[0].data)).toMatchObject({incidente:2,tutor_estudiante:3})
  })
  it('muestra error de carga sin simular éxito', async () => {
    mock.onGet('/estudiantes/inscripciones-disciplina/').reply(500)
    render(<DisciplinaPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo')
  })
  it('ignora respuesta antigua al cambiar estudiante', async () => {
    mock.onGet('/estudiantes/inscripciones-disciplina/').reply(200,page([{id:1,estudiante:4,estudiante_nombre:'Ana Test',curso_nombre:'A'},{id:2,estudiante:5,estudiante_nombre:'Bruno Test',curso_nombre:'B'}]))
    let complete!:(value:[number,unknown])=>void
    mock.onGet('/estudiantes/incidentes/').reply(config=>config.params.estudiante===4
      ? new Promise(resolve=>{complete=resolve})
      : [200,page([{...incident,id:3,descripcion:'Incidente de Bruno'}])])
    render(<DisciplinaPage />)
    fireEvent.change(await screen.findByLabelText('Inscripción'),{target:{value:'1'}})
    await waitFor(()=>expect(complete).toBeDefined())
    fireEvent.change(screen.getByLabelText('Inscripción'),{target:{value:'2'}})
    expect(await screen.findByText('Incidente de Bruno')).toBeInTheDocument()
    await act(async()=>{complete([200,page([incident])])})
    expect(screen.queryByText('Incidente inicial')).not.toBeInTheDocument()
    expect(screen.getByText('Incidente de Bruno')).toBeInTheDocument()
  })
})

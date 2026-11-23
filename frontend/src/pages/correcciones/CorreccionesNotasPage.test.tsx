import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import axios from '../../api/axiosInstance'
import CorreccionesNotasPage from './CorreccionesNotasPage'

let teacher = true
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ isProfesor: () => teacher, can: (_m:string,a:string) => teacher ? a !== 'editar' : a !== 'crear', user: { id: teacher ? 2 : 9 } }) }))
const mock = new MockAdapter(axios)
const grade = {id:1,valor:'60.00',puntaje_maximo:'100.00',estudiante_nombre:'Ana Test',actividad_nombre:'Examen',materia_nombre:'Matemática',curso_nombre:'Tercero A',periodo_nombre:'T1'}
const row = {id:3,calificacion:1,valor_anterior:'60.00',valor_nuevo:'80.00',motivo:'Revisión',estado:'SOLICITADA',solicitado_por:2,solicitante_nombre:'Docente Test',solicitado_at:'2026-03-01T12:00:00Z',detalle_calificacion:grade}
const page = (results:unknown[]) => ({count:results.length,results,next:null,previous:null})
describe('HU18 correcciones', () => {
  beforeEach(() => {
    teacher = true
    mock.onGet('/academico/calificaciones-corregibles/').reply(200,page([grade]))
    mock.onGet('/academico/correcciones/').reply(200,page([row]))
  })
  afterEach(() => mock.reset())
  it('docente solicita corrección y no autoriza', async () => {
    mock.onPost('/academico/correcciones/').reply(201,row)
    render(<CorreccionesNotasPage />)
    fireEvent.click(await screen.findByRole('button',{name:'Nueva solicitud'}))
    fireEvent.change(await screen.findByLabelText('Calificación *'),{target:{value:'1'}})
    fireEvent.change(screen.getByLabelText('Valor propuesto *'),{target:{value:'80'}})
    fireEvent.change(screen.getByLabelText('Motivo *'),{target:{value:'Revisión'}})
    fireEvent.click(screen.getByRole('button',{name:'Enviar solicitud'}))
    expect(await screen.findByText('Solicitud registrada.')).toBeInTheDocument()
    expect(screen.queryByRole('button',{name:'Aprobar solicitud 3'})).not.toBeInTheDocument()
    expect(JSON.parse(mock.history.post[0].data)).toEqual({calificacion:1,valor_nuevo:'80',motivo:'Revisión'})
  })
  it('director confirma aprobación y actualiza estado', async () => {
    teacher = false
    mock.onPost('/academico/correcciones/3/aprobar/').reply(() => {
      mock.onGet('/academico/correcciones/').reply(200,page([{...row,estado:'APROBADA'}]))
      return [200,{...row,estado:'APROBADA'}]
    })
    render(<CorreccionesNotasPage />)
    fireEvent.click(await screen.findByRole('button',{name:'Aprobar solicitud 3'}))
    fireEvent.click(screen.getByRole('button',{name:'Confirmar aprobación'}))
    expect(await screen.findByText('Corrección aprobada.')).toBeInTheDocument()
    expect(await screen.findByText('APROBADA')).toBeInTheDocument()
  })
  it('permiso revocado muestra error y deshabilita autorización', async () => {
    teacher = false
    mock.onPost('/academico/correcciones/3/aprobar/').reply(403,{detail:'Permiso revocado.'})
    render(<CorreccionesNotasPage />)
    fireEvent.click(await screen.findByRole('button',{name:'Aprobar solicitud 3'}))
    fireEvent.click(screen.getByRole('button',{name:'Confirmar aprobación'}))
    expect(await screen.findByRole('alert')).toHaveTextContent('Permiso revocado.')
    expect(screen.queryByText('Corrección aprobada.')).not.toBeInTheDocument()
    expect(screen.queryByRole('button',{name:'Aprobar solicitud 3'})).not.toBeInTheDocument()
  })
  it('conflicto actualiza la solicitud sin repetir aprobación', async () => {
    teacher=false
    mock.onPost('/academico/correcciones/3/aprobar/').reply(()=>{
      mock.onGet('/academico/correcciones/').reply(200,page([{...row,estado:'RECHAZADA'}]))
      return [409,{detail:'Solicitud resuelta por otro usuario.'}]
    })
    render(<CorreccionesNotasPage />)
    fireEvent.click(await screen.findByRole('button',{name:'Aprobar solicitud 3'}))
    fireEvent.click(screen.getByRole('button',{name:'Confirmar aprobación'}))
    expect(await screen.findByText('RECHAZADA')).toBeInTheDocument()
    expect(screen.queryByRole('button',{name:'Confirmar aprobación'})).not.toBeInTheDocument()
    expect(mock.history.post).toHaveLength(1)
  })
  it('doble envío mientras procesa emite una sola aprobación', async () => {
    teacher=false
    let complete!:(value:[number,unknown])=>void
    mock.onPost('/academico/correcciones/3/aprobar/').reply(()=>new Promise(resolve=>{complete=resolve}))
    render(<CorreccionesNotasPage />)
    fireEvent.click(await screen.findByRole('button',{name:'Aprobar solicitud 3'}))
    const button=screen.getByRole('button',{name:'Confirmar aprobación'})
    fireEvent.click(button);fireEvent.click(button)
    await waitFor(()=>expect(mock.history.post).toHaveLength(1))
    expect(button).toBeDisabled()
    complete([200,{...row,estado:'APROBADA'}])
    expect(await screen.findByText('Corrección aprobada.')).toBeInTheDocument()
  })
})

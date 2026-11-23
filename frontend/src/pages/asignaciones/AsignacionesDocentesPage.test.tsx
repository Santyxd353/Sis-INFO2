import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AsignacionesDocentesPage from './AsignacionesDocentesPage'
import * as api from '../../api/asignacionesDocentes'

let profesor = false
let perfil: 'DIRECTOR' | 'SECRETARIA' | 'PROFESOR' | 'OTRO' = 'DIRECTOR'
let permisoCrear = true
let componenteVisible = true
let componenteEditable = true
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({
  isProfesor: () => profesor,
  user: {
    rol: { nombre: perfil === 'SECRETARIA' ? 'Admin' : perfil === 'PROFESOR' ? 'Profesor' : perfil === 'DIRECTOR' ? 'Director' : 'Admin' },
    perfil: { puesto: { nombre: perfil === 'SECRETARIA' ? 'Secretaria' : perfil === 'DIRECTOR' ? 'Director' : null } },
    alcance: { tipo: 'UNIDAD', unidad_id: 1, unidad_nombre: 'Primaria', colegio_id: 1, colegio_nombre: 'Colegio' },
  },
  can: () => permisoCrear,
  puedeComponente: () => componenteVisible,
  puedeEditarComponente: () => componenteEditable,
}) }))
vi.mock('../../api/catalogosInstitucionales', () => ({ listarUnidadesCatalogo: vi.fn() }))
vi.mock('../../api/asignacionesDocentes', () => ({ listarAsignaciones:vi.fn(), listarCalendarios:vi.fn(), listarCursos:vi.fn(), listarProfesores:vi.fn(), listarMateriasCurso:vi.fn(), crearAsignacion:vi.fn(), editarAsignacion:vi.fn(), desactivarAsignacion:vi.fn() }))
const asignacion = { id:1,tipo:'MATERIA' as const,calendario_academico:null,gestion_anio:null,curso:2,curso_nombre:'Primero A',materia_curso:44,materia_nombre:'Matemática',profesor:3,profesor_nombre:'Ana Docente',unidad_educativa:1,unidad_nombre:'Primaria',nivel_educativo:'PRI',fecha_inicio:'2026-02-01',fecha_fin:null,horas_semanales:4,estado:'ACTIVO' as const,created_at:'',updated_at:'',eliminado_at:null }

describe('pantalla de asignaciones docentes', () => {
  beforeEach(() => { perfil='DIRECTOR'; permisoCrear=true; componenteVisible=true; componenteEditable=true })
  it('secretaria con permisos UI editables ve el boton', async () => { perfil='SECRETARIA'; render(<AsignacionesDocentesPage/>); expect(await screen.findByText(/Nueva asignaci/)).toBeInTheDocument() })
  it('secretaria sin permiso editable no ve el boton ni el modal', async () => { perfil='SECRETARIA'; componenteEditable=false; render(<AsignacionesDocentesPage/>); await screen.findAllByText('Ana Docente'); expect(screen.queryByText(/Nueva asignaci/)).not.toBeInTheDocument(); expect(screen.queryByRole('dialog')).not.toBeInTheDocument() })
  it('secretaria con modulo oculto no ve el boton', async () => { perfil='SECRETARIA'; componenteVisible=false; render(<AsignacionesDocentesPage/>); await screen.findAllByText('Ana Docente'); expect(screen.queryByText(/Nueva asignaci/)).not.toBeInTheDocument() })
  it('secretaria sin permiso funcional no ve el boton', async () => { perfil='SECRETARIA'; permisoCrear=false; render(<AsignacionesDocentesPage/>); await screen.findAllByText('Ana Docente'); expect(screen.queryByText(/Nueva asignaci/)).not.toBeInTheDocument() })
  it('secretaria sin configuracion UI no ve el boton', async () => { perfil='SECRETARIA'; componenteVisible=true; componenteEditable=false; render(<AsignacionesDocentesPage/>); await screen.findAllByText('Ana Docente'); expect(screen.queryByText(/Nueva asignaci/)).not.toBeInTheDocument() })
  it('secretaria sin boton mantiene el GET del listado', async () => { perfil='SECRETARIA'; componenteEditable=false; render(<AsignacionesDocentesPage/>); await screen.findAllByText('Ana Docente'); expect(api.listarAsignaciones).toHaveBeenCalled() })
  beforeEach(() => { profesor=false; vi.mocked(api.listarAsignaciones).mockResolvedValue({data:{count:1,next:null,previous:null,results:[asignacion]},status:200,statusText:'OK',headers:{},config:{} as never}); vi.mocked(api.listarCalendarios).mockResolvedValue([{id:1,unidad_educativa:1,unidad_nombre:'Primaria',año:2026,activo:true}]); vi.mocked(api.listarCursos).mockResolvedValue([{id:2,nombre:'Primero A'}]); vi.mocked(api.listarProfesores).mockResolvedValue([{id:3,usuario:{nombre:'Ana',apellido:'Docente'},estado:true}]); vi.mocked(api.listarMateriasCurso).mockResolvedValue([{id:44,curso:2,curso_nombre:'Primero A',materia:8,materia_nombre:'Matemática'}]); vi.mocked(api.crearAsignacion).mockResolvedValue({data:asignacion,status:201,statusText:'OK',headers:{},config:{} as never}); vi.spyOn(window,'confirm').mockReturnValue(true) })
  it('muestra registros históricos sin romper la tabla', async () => { render(<AsignacionesDocentesPage/>); expect(await screen.findByText('Histórica')).toBeInTheDocument() })
  it('profesor ve modo de solo lectura', async () => { profesor=true; render(<AsignacionesDocentesPage/>); await screen.findByText('Ana Docente'); expect(screen.queryByText('Nueva asignación')).not.toBeInTheDocument(); expect(screen.queryByText('Acciones')).not.toBeInTheDocument() })
  it('usuario administrador ve acciones', async () => { render(<AsignacionesDocentesPage/>); expect(await screen.findByText('Nueva asignación')).toBeInTheDocument(); expect(screen.getByLabelText('Editar asignación 1')).toBeInTheDocument() })
  it('consulta materias cuando cambia el curso', async () => { render(<AsignacionesDocentesPage/>); fireEvent.click(await screen.findByText('Nueva asignación')); fireEvent.change(screen.getAllByLabelText('Curso')[1],{target:{value:'2'}}); await waitFor(()=>expect(api.listarMateriasCurso).toHaveBeenCalledWith(2)) })
  it('valida campos obligatorios y materia', async () => { render(<AsignacionesDocentesPage/>); fireEvent.click(await screen.findByText('Nueva asignación')); fireEvent.click(screen.getByText('Guardar')); expect(await screen.findAllByText('Campo obligatorio.')).toHaveLength(4); expect(screen.getByText('Seleccione una materia del curso.')).toBeInTheDocument() })
  it('tutor de curso oculta la materia del formulario', async () => { render(<AsignacionesDocentesPage/>); fireEvent.click(await screen.findByText('Nueva asignación')); fireEvent.change(screen.getAllByLabelText('Tipo')[1],{target:{value:'TUTOR_CURSO'}}); expect(screen.getAllByLabelText('Materia del curso')).toHaveLength(1) })
  it('desactiva con POST de dominio', async () => { vi.mocked(api.desactivarAsignacion).mockResolvedValue({data:{...asignacion,estado:'INACTIVO'},status:200,statusText:'OK',headers:{},config:{} as never}); render(<AsignacionesDocentesPage/>); fireEvent.click(await screen.findByLabelText('Desactivar asignación 1')); await waitFor(()=>expect(api.desactivarAsignacion).toHaveBeenCalledWith(1)) })
  it('envía IDs seleccionados para profesor y curso al backend', async () => {
    const otra = { ...asignacion, id: 2, profesor_nombre: 'Bruno Profesor', curso_nombre: 'Segundo B' }
    vi.mocked(api.listarAsignaciones).mockResolvedValue({data:{count:2,next:null,previous:null,results:[asignacion,otra]},status:200,statusText:'OK',headers:{},config:{} as never})
    render(<AsignacionesDocentesPage/>); await screen.findAllByText('Ana Docente')
    fireEvent.change(screen.getByLabelText('Profesor'), { target: { value: '3' } }); fireEvent.change(screen.getByLabelText('Curso'), { target: { value: '2' } }); fireEvent.click(screen.getByText('Consultar'))
    await waitFor(() => expect(vi.mocked(api.listarAsignaciones)).toHaveBeenLastCalledWith(expect.objectContaining({ profesor: 3, curso: 2 }), expect.anything()))
  })
  it('no muestra un error cuando una solicitud anterior es cancelada', async () => {
    vi.mocked(api.listarAsignaciones).mockRejectedValueOnce(new DOMException('Solicitud cancelada', 'AbortError'))
    render(<AsignacionesDocentesPage />)
    await waitFor(() => expect(api.listarAsignaciones).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })
})


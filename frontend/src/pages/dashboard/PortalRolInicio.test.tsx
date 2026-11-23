import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { listarAsignaciones } from '../../api/asignacionesDocentes'
import { useAuth } from '../../app/contexts/AuthContext'
import type { Usuario } from '../../app/modelos/Usuarios'
import PortalRolInicio from './PortalRolInicio'

vi.mock('../portal/PortalFamiliar', () => ({ default: () => <h1>Portal familiar conectado</h1> }))
vi.mock('../../api/asignacionesDocentes', () => ({ listarAsignaciones: vi.fn() }))
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: vi.fn() }))

const usuario = {
  id: 7, nombre: 'María', apellido: 'Rojas', rol: { id: 3, nombre: 'Profesor' },
  unidad: { id: 2, nombre: 'Secundaria', colegio: { id: 1, nombre: 'Colegio Central' } },
  alcance: { tipo: 'PERSONAL', colegio_id: 1, colegio_nombre: 'Colegio Central', unidad_id: 2, unidad_nombre: 'Secundaria' },
  permisos_efectivos: [],
} as unknown as Usuario
const asignacion = {
  id: 4, tipo: 'MATERIA', calendario_academico: 2, gestion_anio: 2026, curso: 5,
  curso_nombre: 'Primero A', materia_curso: 8, materia_nombre: 'Matemática', profesor: 9,
  profesor_nombre: 'María Rojas', unidad_educativa: 2, unidad_nombre: 'Secundaria',
  fecha_inicio: '2026-02-01', fecha_fin: null, horas_semanales: 5, estado: 'ACTIVO',
  created_at: '', updated_at: '', eliminado_at: null,
}
const respuesta = (results: unknown[] = [asignacion], count = results.length) => Promise.resolve({ data: { count, next: null, previous: null, results } })
const ver = (profile: 'PROFESOR'|'REGENTE'|'TUTOR'|'ESTUDIANTE') => render(<MemoryRouter><PortalRolInicio profile={profile} /></MemoryRouter>)

describe('dashboards personales seguros', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue({ user: usuario } as ReturnType<typeof useAuth>)
    vi.mocked(listarAsignaciones).mockImplementation(() => respuesta() as ReturnType<typeof listarAsignaciones>)
  })

  it('renderiza la identidad del profesor', () => { ver('PROFESOR'); expect(screen.getByText('Panel docente')).toBeInTheDocument(); expect(screen.getByText(/María/)).toBeInTheDocument() })
  it('muestra colegio y unidad del profesor', () => { ver('PROFESOR'); expect(screen.getByText('Colegio Central')).toBeInTheDocument(); expect(screen.getByText('Secundaria')).toBeInTheDocument() })
  it('consulta exclusivamente asignaciones activas propias', async () => { ver('PROFESOR'); await waitFor(() => expect(listarAsignaciones).toHaveBeenCalledWith({ estado: 'ACTIVO', page: 1, page_size: 10 })) })
  it('no envía un identificador manipulable de profesor', async () => { ver('PROFESOR'); await waitFor(() => expect(listarAsignaciones).toHaveBeenCalled()); expect(vi.mocked(listarAsignaciones).mock.calls[0][0]).not.toHaveProperty('profesor') })
  it('presenta el total entregado por el servidor', async () => { vi.mocked(listarAsignaciones).mockImplementation(() => respuesta([asignacion], 6) as ReturnType<typeof listarAsignaciones>); ver('PROFESOR'); expect(await screen.findByText('6')).toBeInTheDocument() })
  it('presenta los datos de la asignación propia', async () => { ver('PROFESOR'); expect(await screen.findByText('Primero A')).toBeInTheDocument(); expect(screen.getByText('Matemática')).toBeInTheDocument() })
  it('no muestra crear asignación', () => { ver('PROFESOR'); expect(screen.queryByText(/Nueva asignación/i)).not.toBeInTheDocument() })
  it('no muestra editar ni desactivar', () => { ver('PROFESOR'); expect(screen.queryByText(/^Editar$/i)).not.toBeInTheDocument(); expect(screen.queryByText(/Desactivar/i)).not.toBeInTheDocument() })
  it('muestra estado vacío del profesor', async () => { vi.mocked(listarAsignaciones).mockImplementation(() => respuesta([]) as ReturnType<typeof listarAsignaciones>); ver('PROFESOR'); expect(await screen.findByText('Todavía no tiene asignaciones académicas registradas')).toBeInTheDocument() })
  it('permite actualizar la lista', async () => { ver('PROFESOR'); await waitFor(() => expect(listarAsignaciones).toHaveBeenCalledTimes(1)); fireEvent.click(screen.getByRole('button', { name: 'Actualizar mis asignaciones' })); await waitFor(() => expect(listarAsignaciones).toHaveBeenCalledTimes(2)) })
  it('ofrece acceso de lectura a asignaciones', () => { ver('PROFESOR'); expect(screen.getByRole('link', { name: 'Consultar mis asignaciones' })).toHaveAttribute('href', '/dashboard/asignaciones-docentes') })
  it('mantiene la sesión y muestra acceso restringido ante 403', async () => { vi.mocked(listarAsignaciones).mockRejectedValue({ isAxiosError: true, response: { status: 403 } }); ver('PROFESOR'); expect(await screen.findByText('No tiene permisos para acceder a esta funcionalidad')).toBeInTheDocument() })
  it('ofrece reintento ante error de red', async () => { vi.mocked(listarAsignaciones).mockRejectedValue(new Error('red')); ver('PROFESOR'); fireEvent.click(await screen.findByRole('button', { name: 'Reintentar' })); await waitFor(() => expect(listarAsignaciones).toHaveBeenCalledTimes(2)) })
  it('no muestra módulos docentes deshabilitados', () => { ver('PROFESOR'); expect(screen.queryByText('Calificaciones')).not.toBeInTheDocument(); expect(screen.queryByText('Asistencia')).not.toBeInTheDocument() })

  it('renderiza la identidad del regente', () => { ver('REGENTE'); expect(screen.getByText('Panel de regencia')).toBeInTheDocument(); expect(screen.getByText('Colegio Central')).toBeInTheDocument() })
  it('muestra el estado operativo vacío del regente', () => { ver('REGENTE'); expect(screen.getByText('No tiene módulos operativos habilitados actualmente')).toBeInTheDocument() })
  it('el regente no muestra asistencia ni disciplina deshabilitadas', () => { ver('REGENTE'); expect(screen.queryByText(/^Asistencia$/)).not.toBeInTheDocument(); expect(screen.queryByText(/^Disciplina$/)).not.toBeInTheDocument() })
  it('el regente no consulta endpoints personales', () => { ver('REGENTE'); expect(listarAsignaciones).not.toHaveBeenCalled() })

  it('renderiza identidad y estado seguro del tutor', () => { ver('TUTOR'); expect(screen.getByText('Portal familiar conectado')).toBeInTheDocument() })
  it('el tutor no consulta asignaciones ni estudiantes generales', () => { ver('TUTOR'); expect(listarAsignaciones).not.toHaveBeenCalled(); expect(screen.queryByText('Mis asignaciones')).not.toBeInTheDocument() })
  it('el tutor no muestra auditoría ni módulos deshabilitados', () => { ver('TUTOR'); expect(screen.queryByText(/Auditoría/)).not.toBeInTheDocument(); expect(screen.queryByText(/^Horarios$/)).not.toBeInTheDocument() })

  it('renderiza identidad y estado seguro del estudiante', () => { ver('ESTUDIANTE'); expect(screen.getByText('Portal familiar conectado')).toBeInTheDocument() })
  it('el estudiante no consulta listados administrativos', () => { ver('ESTUDIANTE'); expect(listarAsignaciones).not.toHaveBeenCalled(); expect(screen.queryByText('Mis asignaciones')).not.toBeInTheDocument() })
  it('el estudiante no muestra edición, finanzas ni módulos deshabilitados', () => { ver('ESTUDIANTE'); expect(screen.queryByText(/Editar/)).not.toBeInTheDocument(); expect(screen.queryByText(/Finanzas/)).not.toBeInTheDocument(); expect(screen.queryByText(/^Calificaciones$/)).not.toBeInTheDocument() })
})

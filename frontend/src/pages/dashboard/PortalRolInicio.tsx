import axios from 'axios'
import { BookOpenCheck, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listarAsignaciones, type AsignacionDocente } from '../../api/asignacionesDocentes'
import { useAuth } from '../../app/contexts/AuthContext'
import { resolveVisualProfile } from '../../app/navigation/navigationConfig'
import type { VisualProfile } from '../../app/navigation/types'
import PortalFamiliar from '../portal/PortalFamiliar'
import { DashboardEmptyState, DashboardErrorState, DashboardMetricCard, DashboardSection, InstitutionalIdentity } from './components/DashboardComponents'

const configuracion: Partial<Record<VisualProfile, { titulo: string; descripcion: string }>> = {
  PROFESOR: { titulo: 'Panel docente', descripcion: 'Consulte sus asignaciones académicas.' },
  REGENTE: { titulo: 'Panel de regencia', descripcion: 'Seguimiento institucional de la unidad educativa.' },
  TUTOR: { titulo: 'Portal de familias', descripcion: 'Información vinculada a su familia.' },
  ESTUDIANTE: { titulo: 'Mi información académica', descripcion: 'Consulta personal de su actividad académica.' },
}

export default function PortalRolInicio({ profile }: { profile?: VisualProfile }) {
  const { user } = useAuth()
  const perfil = profile ?? resolveVisualProfile(user)
  if (perfil === 'TUTOR' || perfil === 'ESTUDIANTE') return <PortalFamiliar />
  const texto = configuracion[perfil] ?? { titulo: 'Portal educativo', descripcion: 'Información de su cuenta.' }
  return <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
    <InstitutionalIdentity title={texto.titulo} description={`${user?.nombre ?? 'Usuario'} · ${texto.descripcion}`} college={user?.alcance?.colegio_nombre??user?.unidad?.colegio?.nombre} unit={user?.alcance?.unidad_nombre??user?.unidad?.nombre} role={user?.perfil?.puesto?.nombre ?? user?.puesto?.nombre ?? user?.rol.nombre} scopeText={perfil==='PROFESOR'?'Alcance: información personal':undefined} />
    {perfil === 'PROFESOR' && <PanelProfesor />}
    {perfil === 'REGENTE' && <DashboardSection title="Módulos operativos"><DashboardEmptyState message="No tiene módulos operativos habilitados actualmente" /></DashboardSection>}
  </main>
}

function PanelProfesor() {
  const [asignaciones, setAsignaciones] = useState<AsignacionDocente[]>([])
  const [total, setTotal] = useState<number>()
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<'restricted' | 'network' | null>(null)
  const cargar = useCallback(async () => {
    setCargando(true); setError(null)
    try { const { data } = await listarAsignaciones({ estado: 'ACTIVO', page: 1, page_size: 10 }); setAsignaciones(data.results); setTotal(data.count) }
    catch (e) { setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'restricted' : 'network') }
    finally { setCargando(false) }
  }, [])
  // La carga inicial sincroniza esta vista con el recurso remoto del profesor.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar() }, [cargar])
  return <>
    <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><DashboardMetricCard title="Asignaciones activas" value={total} description="Total de asignaciones académicas propias" icon={BookOpenCheck} loading={cargando} error={error !== null} /></div>
    <DashboardSection title="Mis asignaciones" description="Se muestran exclusivamente las asignaciones asociadas a su cuenta.">
      <div className="mb-3 flex flex-wrap justify-end gap-2"><button type="button" onClick={() => void cargar()} className="btn-secondary" aria-label="Actualizar mis asignaciones"><RefreshCw size={17} />Actualizar lista</button><Link to="/dashboard/asignaciones-docentes" className="btn-primary">Consultar mis asignaciones</Link></div>
      {error && <div className="space-y-3"><DashboardErrorState restricted={error === 'restricted'} />{error === 'network' && <button type="button" className="btn-secondary" onClick={() => void cargar()}>Reintentar</button>}</div>}
      {!error && cargando && <p role="status" className="rounded-2xl bg-white p-7 text-center text-slate-500">Cargando asignaciones...</p>}
      {!error && !cargando && asignaciones.length === 0 && <DashboardEmptyState message="Todavía no tiene asignaciones académicas registradas" />}
      {!error && !cargando && asignaciones.length > 0 && <div className="overflow-x-auto rounded-2xl bg-white shadow-sm"><table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr>{['Gestión','Curso','Materia','Tipo','Inicio','Final','Horas','Estado'].map(c => <th key={c} className="px-4 py-3">{c}</th>)}</tr></thead><tbody>{asignaciones.map(a => <tr key={a.id} className="border-t border-slate-100"><td className="px-4 py-3">{a.gestion_anio ?? '—'}</td><td className="px-4 py-3">{a.curso_nombre}</td><td className="px-4 py-3">{a.materia_nombre ?? '—'}</td><td className="px-4 py-3">{a.tipo === 'MATERIA' ? 'Materia' : 'Tutoría'}</td><td className="px-4 py-3">{a.fecha_inicio}</td><td className="px-4 py-3">{a.fecha_fin ?? 'Vigente'}</td><td className="px-4 py-3">{a.horas_semanales ?? '—'}</td><td className="px-4 py-3">{a.estado}</td></tr>)}</tbody></table></div>}
    </DashboardSection>
  </>
}

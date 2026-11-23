import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { obtenerBoletin, obtenerPortalFamiliar, type BoletinPortal, type FiltrosFamilia, type PortalFamilia } from '../../api/portal'
import { useAuth } from '../../app/contexts/AuthContext'
import { DashboardEmptyState, DashboardSection } from '../dashboard/components/DashboardComponents'
import { CalendarFilters, PortalMetric, PortalSelect, PortalStatus, PortalTable, UpdatedAt } from './PortalUI'
import { usePortal } from './usePortal'

export default function PortalFamiliar() {
  const { user } = useAuth()
  return <FamilyPortal key={`${user?.id}:${user?.alcance?.colegio_id}:${user?.alcance?.unidad_id}`} />
}
function FamilyPortal() {
  const { data, loading, error, select, reload } = usePortal<PortalFamilia, FiltrosFamilia>(obtenerPortalFamiliar)
  const student = data?.seleccionado ?? undefined, calendar = data?.gestion?.id
  return <section aria-labelledby="portal-familia-title" className="mx-auto max-w-7xl space-y-6 px-4 py-7 sm:px-6 lg:px-8">
    <header className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-widest text-brand-700">Comunidad educativa</p><h1 id="portal-familia-title" className="mt-2 text-3xl font-bold">Portal familiar</h1><p className="mt-2 text-slate-600">Consulte la información académica de los estudiantes vinculados a su cuenta.</p></div><button type="button" className="btn-secondary" onClick={reload} disabled={loading}>Actualizar portal</button></header>
    <PortalStatus loading={loading} error={error} retry={reload} title="portal familiar" />
    {data && <><div className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-3"><PortalSelect label="Estudiante" value={data.seleccionado ?? ''} onChange={id => select(id ? { estudiante: id } : {})} disabled={!data.estudiantes.length}>{!data.estudiantes.length && <option value="">Sin estudiantes</option>}{data.estudiantes.map(row => <option key={row.id} value={row.id}>{row.nombre}</option>)}</PortalSelect><CalendarFilters gestiones={data.gestiones} gestion={calendar ?? ''} periodos={data.periodos} periodo={data.periodo ?? ''} onGestion={id => select({ estudiante: student, calendario_academico: id })} onPeriodo={id => select({ estudiante: student, calendario_academico: calendar, ...(id ? { periodo: id } : {}) })} /></div>
      {data.estudiante ? <FamilyDetails data={data} /> : <DashboardEmptyState message="No hay estudiantes vinculados a esta cuenta." />}
      <UpdatedAt date={data.actualizado_at} /></>}
  </section>
}
function FamilyDetails({ data }: { data: PortalFamilia }) {
  const student = data.estudiante!, attendance = data.asistencia
  const period = data.periodos.find(row => row.id === data.periodo)?.nombre ?? 'Toda la gestión'
  const days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
  return <><header className="rounded-xl border border-brand-200 bg-brand-50 p-5"><h2 className="text-2xl font-bold">{student.nombre}</h2><p className="mt-1 text-slate-700">{student.unidad_nombre} · {student.curso ?? 'Sin curso registrado'}</p><p className="mt-2 text-sm text-brand-800">{data.gestion ? `Gestión ${data.gestion.anio}` : 'Sin gestión académica'} · {period}</p></header>
    <DashboardSection title="Notas" description="Calificaciones registradas para la gestión y el periodo seleccionados.">{data.notas.length ? <PortalTable caption="Notas del estudiante seleccionado" columns={['Materia', 'Periodo', 'Nota', 'Condición']}>{data.notas.flatMap((row, index) => [...row.periodos.map(p => <tr key={`${index}-${p.id}`}><td className="font-semibold">{row.materia}</td><td>{p.nombre}</td><td>{p.nota}</td><td>{p.condicion}</td></tr>), ...(row.anual ? [<tr key={`${index}-anual`} className="bg-slate-50"><td className="font-semibold">{row.materia}</td><td>Anual</td><td>{row.anual.nota}</td><td>{row.anual.condicion}</td></tr>] : [])])}</PortalTable> : <DashboardEmptyState message="No hay notas registradas para esta selección." />}</DashboardSection>
    <DashboardSection title="Horario" description="Asignaciones vigentes de la gestión seleccionada.">{data.horarios.length ? <PortalTable caption="Horario del estudiante seleccionado" columns={['Día', 'Hora', 'Materia', 'Docente', 'Aula']}>{data.horarios.map(row => <tr key={row.id}><td>{days[row.dia - 1] ?? `Día ${row.dia}`}</td><td className="whitespace-nowrap">{row.hora_inicio.slice(0, 5)}–{row.hora_fin.slice(0, 5)}</td><td>{row.materia}</td><td>{row.docente || 'Sin docente'}</td><td>{row.aula || 'Sin aula'}</td></tr>)}</PortalTable> : <DashboardEmptyState message="No hay horarios vigentes para esta gestión." />}</DashboardSection>
    <DashboardSection title="Asistencia" description={attendance.fuente === 'SESIONES' ? 'Registros por sesión de clase. Resumen de todos los registros filtrados; se muestran los últimos 50.' : attendance.fuente === 'LEGACY' ? 'Registro diario histórico. Resumen de todos los registros filtrados; se muestran los últimos 50.' : 'No hay registros de asistencia para esta selección.'}><div className="mb-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6"><PortalMetric title="Asistencia registrada" value={attendance.porcentaje} suffix="%" /><PortalMetric title="Presentes" value={attendance.presentes} /><PortalMetric title="Faltas" value={attendance.faltas} /><PortalMetric title="Atrasos" value={attendance.atrasos} /><PortalMetric title="Licencias" value={attendance.licencias} /><PortalMetric title="Total de registros" value={attendance.total} /></div>{attendance.registros.length > 0 && <PortalTable caption="Últimos registros de asistencia" columns={['Fecha', 'Materia', 'Estado']}>{attendance.registros.map(row => <tr key={row.id}><td>{row.fecha}</td><td>{row.materia || 'Registro diario'}</td><td>{row.estado}</td></tr>)}</PortalTable>}</DashboardSection>
    <DashboardSection title="Boletines" description="Últimos 10 documentos emitidos. Descarga privada para su cuenta."><Boletines items={data.boletines} /></DashboardSection>
    <div className="grid items-start gap-6 lg:grid-cols-2"><DashboardSection title="Comunicados" description="Últimos comunicados disponibles para su cuenta.">{data.comunicados.length ? <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">{data.comunicados.map(row => <li key={row.id} className="p-4"><Link className="font-semibold text-brand-800 underline" to={`/dashboard/comunicaciones?comunicado=${row.id}`}>{row.titulo}</Link><p className="mt-1 text-xs text-slate-600">{row.prioridad === 'URGENTE' ? 'Urgente' : 'Normal'} · {row.leido_at ? 'Lectura confirmada' : 'Pendiente de lectura'}</p></li>)}</ul> : <DashboardEmptyState message="No hay comunicados disponibles." />}<Link className="mt-3 inline-block text-sm font-semibold text-brand-800 underline" to="/dashboard/comunicaciones">Ver todos los comunicados</Link></DashboardSection>
    <DashboardSection title="Notificaciones"><Link className="btn-secondary mb-4" to="/dashboard/notificaciones">{data.notificaciones.no_leidas} sin leer · Abrir notificaciones</Link>{data.notificaciones.recientes.length ? <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">{data.notificaciones.recientes.map(row => <li key={row.id} className="p-4"><Link className="font-semibold text-brand-800 underline" to={row.comunicado ? `/dashboard/comunicaciones?comunicado=${row.comunicado}` : '/dashboard/notificaciones'}>{row.titulo}</Link><p className="mt-1 text-xs text-slate-600">{row.leida_at ? 'Leída' : 'Sin leer'} · <time dateTime={row.created_at}>{new Date(row.created_at).toLocaleDateString('es-BO')}</time></p></li>)}</ul> : <DashboardEmptyState message="No hay notificaciones recientes." />}</DashboardSection></div>
    <DashboardSection title="Pagos no disponibles"><p className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">{data.pagos.mensaje}</p></DashboardSection>
  </>
}
function Boletines({ items }: { items: BoletinPortal[] }) {
  const [busy, setBusy] = useState<number | null>(null), [error, setError] = useState('')
  const pending = useRef<AbortController | null>(null)
  useEffect(() => () => pending.current?.abort(), [])
  async function download(item: BoletinPortal) {
    const controller = new AbortController()
    pending.current?.abort(); pending.current = controller
    setBusy(item.id); setError('')
    try {
      const blob = await obtenerBoletin(item.id, controller.signal)
      if (controller.signal.aborted) return
      const url = URL.createObjectURL(blob)
      try {
        const anchor = document.createElement('a')
        anchor.href = url; anchor.download = `boletin_${item.id}_v${item.version}.pdf`
        document.body.appendChild(anchor)
        try { anchor.click() } finally { anchor.remove() }
      } finally { URL.revokeObjectURL(url) }
    } catch { if (!controller.signal.aborted) setError('No se pudo descargar el boletín. Intente nuevamente.') }
    finally { if (!controller.signal.aborted) setBusy(null) }
  }
  return <>{error && <p role="alert" className="mb-3 rounded-xl bg-amber-50 p-4 text-amber-900">{error}</p>}{items.length ? <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">{items.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 p-4"><div><p className="font-semibold">{row.periodo ?? 'Boletín anual'} · Versión {row.version}</p><p className="mt-1 text-xs text-slate-500">Emitido el {new Date(row.created_at).toLocaleDateString('es-BO')}</p></div><button type="button" className="btn-secondary" aria-label={`Descargar boletín ${row.id}`} disabled={busy !== null} onClick={() => void download(row)}>{busy === row.id ? 'Descargando...' : 'Descargar PDF'}</button></li>)}</ul> : <DashboardEmptyState message="No hay boletines emitidos para esta selección." />}</>
}

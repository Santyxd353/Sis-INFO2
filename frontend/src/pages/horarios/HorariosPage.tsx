import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import { eliminarHorario, type Horario, type OpcionHorario } from '../../api/horarios'
import { useOperation, usePaged } from '../workflows/useWorkflow'
import { Errors, Field, Pages, Status } from '../workflows/WorkflowUI'
import CatalogoHorario from './CatalogoHorario'
import HorarioForm from './HorarioForm'
import '../workflows/workflows.css'

const days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
function isoDate(date: Date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
function monday(value: string) { const date = new Date(`${value}T12:00:00`); date.setDate(date.getDate() - (date.getDay() + 6) % 7); return isoDate(date) }
function shift(value: string, days: number) { const date = new Date(`${value}T12:00:00`); date.setDate(date.getDate() + days); return isoDate(date) }
export default function HorariosPage() {
  const { can } = useAuth()
  const [week, setWeek] = useState(() => monday(isoDate(new Date())))
  const [course, setCourse] = useState<OpcionHorario | null>(null), [teacher, setTeacher] = useState<OpcionHorario | null>(null), [year, setYear] = useState('')
  const [page, setPage] = useState(1), [revision, setRevision] = useState(0)
  const [editing, setEditing] = useState<Horario | true | null>(null), [deleting, setDeleting] = useState<Horario | null>(null), [success, setSuccess] = useState(''), [denied, setDenied] = useState(false)
  const data = usePaged<Horario>('/academico/horarios/', { semana: week, curso: course?.id ? String(course.id) : '', profesor: teacher?.id ? String(teacher.id) : '', gestion: year, page }, revision)
  const writable = can('horario', 'crear') || can('horario', 'editar') || can('horario', 'eliminar')
  function changeWeek(value: string) { if (value) { setWeek(monday(value)); setPage(1) } }
  function saved() { setEditing(null); setSuccess(editing === true ? 'Horario creado.' : 'Horario actualizado.'); setRevision(v => v + 1) }
  return <main className="wf-page space-y-6">
    <header className="flex flex-wrap items-center justify-between gap-4"><div><h1>Horarios</h1><p className="mt-2 text-slate-600">Planificación semanal por docente, curso y aula.</p>{!writable && <p className="mt-2 text-sm text-slate-600">Solo lectura · Consulte los horarios disponibles para su cuenta.</p>}</div>{can('horario', 'crear') && !editing && <button className="wf-primary" disabled={denied} onClick={() => { setEditing(true); setSuccess('') }}>Nuevo horario</button>}</header>
    {success && <p role="status" className="wf-success">{success}</p>}
    {editing && <HorarioForm key={editing === true ? 'new' : editing.id} initial={editing === true ? undefined : editing} onDone={saved} onCancel={() => setEditing(null)} onDenied={() => setDenied(true)} />}
    <section aria-label="Filtros de horarios" className="wf-card grid items-start gap-5 md:grid-cols-2 xl:grid-cols-3">
      <CatalogoHorario label="Curso" endpoint="/academico/horarios-cursos/" value={course} onChange={value => { setCourse(value); setPage(1) }} />
      <CatalogoHorario label="Profesor" endpoint="/academico/horarios-profesores/" value={teacher} onChange={value => { setTeacher(value); setPage(1) }} />
      <Field label="Gestión"><input className="wf-input" type="number" min="1900" max="9999" placeholder="Todas las gestiones" value={year} onChange={e => { setYear(e.target.value); setPage(1) }} /></Field>
    </section>
    <section aria-label="Semana del horario" className="wf-card flex flex-wrap items-end justify-between gap-4"><div><Field label="Semana"><input className="wf-input" type="date" value={week} onChange={e => changeWeek(e.target.value)} /></Field><p className="mt-2 text-sm text-slate-600">Del {week} al {shift(week, 6)}</p></div><div className="flex flex-wrap gap-3"><button type="button" className="wf-secondary" onClick={() => changeWeek(shift(week, -7))}>Semana anterior</button><button type="button" className="wf-secondary" onClick={() => changeWeek(isoDate(new Date()))}>Hoy</button><button type="button" className="wf-secondary" onClick={() => changeWeek(shift(week, 7))}>Semana siguiente</button></div></section>
    <div aria-busy={data.loading}><Status loading={data.loading} error={data.error} empty={!data.items.length} />{data.error && <button className="wf-secondary mt-3" onClick={() => setRevision(v => v + 1)}>Reintentar</button>}</div>
    {!data.loading && !data.error && data.items.length > 0 && <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">{days.map((day, index) => {
      const rows = data.items.filter(item => item.dia === index + 1).sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio))
      return <section aria-label={`${day} ${shift(week, index)}`} key={day} className="wf-card min-w-0 space-y-4"><div><h2>{day}</h2><p className="text-sm text-slate-600">{shift(week, index)}</p></div>{rows.length ? rows.map(row => <article key={row.id} className="rounded-xl border border-brand-100 bg-brand-50/40 p-4 space-y-2"><p className="font-semibold tabular-nums text-brand-800">{row.hora_inicio.slice(0, 5)} – {row.hora_fin.slice(0, 5)}</p><h3 className="font-semibold">{row.materia_nombre || 'Asignación docente'}</h3><p>{row.curso_nombre}</p><p className="text-sm text-slate-600">{row.profesor_nombre} · {row.aula_nombre}</p><p className="text-xs text-slate-600">Gestión {row.gestion} · Vigente: {row.fecha_inicio} al {row.fecha_fin}</p><div className="flex flex-wrap gap-2">{can('horario', 'editar') && <button className="wf-secondary" disabled={denied || Boolean(editing)} aria-label={`Editar horario ${row.id}`} onClick={() => { setEditing(row); setSuccess('') }}>Editar</button>}{can('horario', 'eliminar') && <button className="wf-secondary text-red-800" disabled={denied || Boolean(editing)} aria-label={`Eliminar horario ${row.id}`} onClick={() => { setDeleting(row); setSuccess('') }}>Eliminar</button>}</div></article>) : <p className="text-sm text-slate-500">Sin clases en esta página.</p>}</section>
    })}</div>}
    <div role="navigation" aria-label="Horarios paginados"><Pages page={page} count={data.count} onChange={setPage} /></div>
    {deleting && <DeleteConfirmation row={deleting} onCancel={() => setDeleting(null)} onDenied={() => setDenied(true)} onDone={() => { setDeleting(null); setSuccess('Horario eliminado.'); setPage(1); setRevision(v => v + 1) }} />}
  </main>
}

function DeleteConfirmation({ row, onCancel, onDone, onDenied }: { row: Horario; onCancel: () => void; onDone: () => void; onDenied: () => void }) {
  const op = useOperation()
  const cancel = useRef<HTMLButtonElement>(null), confirm = useRef<HTMLButtonElement>(null)
  useEffect(() => { cancel.current?.focus(); return () => { document.querySelector<HTMLButtonElement>(`[aria-label="Eliminar horario ${row.id}"]`)?.focus() } }, [row.id])
  return <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/50 p-4"><section role="dialog" aria-modal="true" aria-labelledby="delete-horario-title" className="wf-card w-full max-w-lg space-y-4" onKeyDown={e => { if (e.key === 'Escape' && !op.busy) onCancel(); if (e.key === 'Tab') { const target = e.shiftKey ? confirm.current : cancel.current; const edge = e.shiftKey ? cancel.current : confirm.current; if (document.activeElement === edge || op.denied) { e.preventDefault(); target?.focus() } } }}>
    <h2 id="delete-horario-title">Eliminar horario</h2><p>¿Eliminar el horario de {row.materia_nombre} para {row.curso_nombre}, {days[row.dia - 1]} de {row.hora_inicio.slice(0, 5)} a {row.hora_fin.slice(0, 5)}?</p><Errors errors={op.errors} />
    <div className="flex flex-wrap gap-3"><button ref={cancel} className="wf-secondary" disabled={op.busy} onClick={onCancel}>Cancelar</button><button ref={confirm} className="wf-primary" disabled={op.busy || op.denied} onClick={() => void op.run(() => eliminarHorario(row.id), onDone, status => { if (status === 403) onDenied() })}>{op.busy ? 'Eliminando...' : 'Confirmar eliminación'}</button></div>
  </section></div>
}

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CATEGORIAS, leerNotificacion, type Categoria, type Notificacion, type Preferencias } from '../../api/comunicacion'
import { Errors, Field, Pages, Status } from '../workflows/WorkflowUI'
import { useOperation, usePaged } from '../workflows/useWorkflow'
import { fechaComunicacion, useGestorComunicacion, useRecurso } from './useComunicacion'
import PreferenciasForm from './PreferenciasForm'
import AlertaForm from './AlertaForm'
import '../workflows/workflows.css'

export default function NotificacionesPage() {
  const manager = useGestorComunicacion()
  const [tipo, setTipo] = useState(''), [unread, setUnread] = useState(false), [page, setPage] = useState(1)
  const [revision, setRevision] = useState(0), [prefsOpen, setPrefsOpen] = useState(false), [alertOpen, setAlertOpen] = useState(false)
  const [prefsRevision, setPrefsRevision] = useState(0)
  const [success, setSuccess] = useState('')
  const list = usePaged<Notificacion>('/comunicacion/notificaciones/', { page, ...(tipo ? { tipo } : {}), ...(unread ? { no_leidas: 'true' } : {}) }, revision)
  const summary = useRecurso<{ no_leidas: number }>('/comunicacion/notificaciones/resumen/', revision)
  const prefs = useRecurso<Preferencias>('/comunicacion/preferencias/', prefsRevision, prefsOpen)
  function reload() { setRevision(v => v + 1) }
  function togglePreferences() {
    if (!prefsOpen) setPrefsRevision(v => v + 1)
    setPrefsOpen(v => !v)
  }
  return <section className="wf-page space-y-6" aria-labelledby="notificaciones-title">
    <header className="flex flex-wrap items-center justify-between gap-4"><div><h1 id="notificaciones-title">Notificaciones</h1><p className="mt-2 text-slate-600">Alertas y novedades de su comunidad educativa.</p>{summary.data && <p role="status" className="mt-2 font-semibold text-brand-800">{summary.data.no_leidas} sin leer</p>}{summary.error && <p role="alert">No se pudo cargar el conteo. <button className="underline" onClick={reload}>Reintentar conteo</button></p>}</div><div className="flex flex-wrap gap-3"><Link className="wf-secondary" to="/dashboard/comunicaciones">Ver comunicados</Link><button className="wf-secondary" aria-expanded={prefsOpen} onClick={togglePreferences}>Preferencias de avisos</button>{manager && <button className="wf-primary" aria-expanded={alertOpen} onClick={() => { setAlertOpen(v => !v); setSuccess('') }}>Emitir alerta administrativa</button>}</div></header>
    {success && <p role="status" className="wf-success">{success}</p>}
    {prefsOpen && <><Status loading={prefs.loading} error={prefs.error} empty={false} />{prefs.error && <button className="wf-secondary" onClick={() => setPrefsRevision(v => v + 1)}>Reintentar preferencias</button>}{prefs.data && <PreferenciasForm key={prefsRevision} initial={prefs.data} />}</>}
    {manager && alertOpen && <AlertaForm onCancel={() => setAlertOpen(false)} onDone={created => { setAlertOpen(false); setSuccess(`Alerta registrada: ${created} avisos creados.`); reload() }} />}
    <section aria-label="Filtros de notificaciones" className="wf-card flex flex-wrap items-end gap-4"><div className="min-w-56"><Field label="Categoría"><select className="wf-input" value={tipo} onChange={e => { setTipo(e.target.value); setPage(1) }}><option value="">Todas las categorías</option>{(Object.keys(CATEGORIAS) as Categoria[]).map(category => <option key={category} value={category}>{CATEGORIAS[category]}</option>)}</select></Field></div><label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={unread} onChange={e => { setUnread(e.target.checked); setPage(1) }} />Solo sin leer</label><button className="wf-secondary" onClick={reload}>Actualizar</button></section>
    <Status loading={list.loading} error={list.error} empty={!list.items.length} />{list.error && <button className="wf-secondary" onClick={reload}>Reintentar</button>}
    {!list.loading && !list.error && <div className="grid gap-4 md:grid-cols-2">{list.items.map(row => <Aviso key={`${row.id}|${revision}`} row={row} onRead={reload} />)}</div>}
    <Pages page={page} count={list.count} onChange={setPage} />
  </section>
}

function Aviso({ row, onRead }: { row: Notificacion; onRead: () => void }) {
  const op = useOperation()
  return <article className={`wf-card space-y-3 ${row.leida_at ? '' : 'border-l-4 border-l-brand-600'}`}><div className="flex flex-wrap justify-between gap-2 text-sm"><span className="font-semibold text-brand-800">{CATEGORIAS[row.tipo] ?? row.tipo}</span><span>{row.leida_at ? 'Leída' : 'Sin leer'}</span></div><h2>{row.titulo}</h2><p className="whitespace-pre-wrap">{row.cuerpo}</p><p className="text-sm text-slate-500">{fechaComunicacion(row.created_at)}</p><Errors errors={op.errors} /><div className="flex flex-wrap gap-3">{!row.leida_at && <button className="wf-secondary" disabled={op.busy || op.denied} onClick={() => void op.run(() => leerNotificacion(row.id), onRead)}>{op.busy ? 'Marcando...' : 'Marcar como leída'}</button>}{row.comunicado && <Link className="wf-primary" to={`/dashboard/comunicaciones?comunicado=${row.comunicado}`}>Abrir comunicado</Link>}</div>{row.comunicado && <p className="text-xs text-slate-600">La lectura del comunicado se confirma por separado al abrir su contenido.</p>}</article>
}

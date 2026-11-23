import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { archivarComunicado, confirmarLectura, publicarComunicado, type Comunicado } from '../../api/comunicacion'
import { Errors, Pages, Status } from '../workflows/WorkflowUI'
import { useOperation, usePaged } from '../workflows/useWorkflow'
import ComunicadoForm from './ComunicadoForm'
import { fechaComunicacion, useGestorComunicacion, useRecurso } from './useComunicacion'
import '../workflows/workflows.css'

export default function ComunicadosPage() {
  const manager = useGestorComunicacion()
  const [search, setSearch] = useSearchParams()
  const selected = Number(search.get('comunicado')) || null
  const [page, setPage] = useState(1), [revision, setRevision] = useState(0)
  const [editing, setEditing] = useState<Comunicado | 'new' | null>(null)
  const [success, setSuccess] = useState('')
  const list = usePaged<Comunicado>('/comunicacion/comunicados/', { page }, revision)
  function reload() { setRevision(v => v + 1) }
  return <section className="wf-page space-y-6" aria-labelledby="comunicados-title">
    <header className="flex flex-wrap items-center justify-between gap-4"><div><h1 id="comunicados-title">Comunicados</h1><p className="mt-2 text-slate-600">Información de su institución y de los cursos vinculados a su cuenta.</p></div><div className="flex flex-wrap gap-3"><Link className="wf-secondary" to="/dashboard/notificaciones">Ver notificaciones</Link>{manager && !editing && <button className="wf-primary" onClick={() => { setEditing('new'); setSuccess('') }}>Nuevo comunicado</button>}</div></header>
    {success && <p role="status" className="wf-success">{success}</p>}
    {editing && manager && <ComunicadoForm key={editing === 'new' ? 'new' : editing.id} initial={editing === 'new' ? undefined : editing} onCancel={() => setEditing(null)} onDone={() => { setEditing(null); setSuccess('Borrador guardado.'); reload() }} />}
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <div className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-2"><h2>Disponibles para su cuenta</h2><button className="wf-secondary" onClick={reload}>Actualizar</button></div><Status loading={list.loading} error={list.error} empty={!list.items.length} />{list.error && <button className="wf-secondary" onClick={reload}>Reintentar</button>}
        {!list.loading && !list.error && list.items.map(row => <article key={row.id} className={`wf-card space-y-2 ${selected === row.id ? 'ring-2 ring-brand-600' : ''}`}><div className="flex flex-wrap gap-2 text-xs font-semibold"><span>{row.estado}</span><span>{row.prioridad === 'URGENTE' ? 'Urgente' : 'Normal'}</span>{row.leido_at && <span className="text-green-800">Lectura confirmada</span>}</div><h3 className="font-semibold text-lg">{row.titulo}</h3><p className="text-sm text-slate-600">{row.curso ? 'Dirigido a un curso' : 'Toda la unidad educativa'} · {fechaComunicacion(row.publicado_at ?? row.created_at)}</p><button className="wf-secondary" aria-label={`Abrir ${row.titulo}`} onClick={() => { setSearch({ comunicado: String(row.id) }); setSuccess('') }}>Abrir comunicado</button></article>)}
        <Pages page={page} count={list.count} onChange={setPage} />
      </div>
      {selected ? <DetalleComunicado key={selected} id={selected} revision={revision} manager={manager} onClose={() => setSearch({})} onEdit={row => { setEditing(row); setSuccess('') }} onChanged={reload} /> : <div className="wf-card text-slate-600">Seleccione un comunicado para consultar su contenido y confirmar la lectura.</div>}
    </div>
  </section>
}

function DetalleComunicado({ id, revision, manager, onClose, onEdit, onChanged }: { id: number; revision: number; manager: boolean; onClose: () => void; onEdit: (row: Comunicado) => void; onChanged: () => void }) {
  const [refresh, setRefresh] = useState(0)
  const resource = useRecurso<Comunicado>(`/comunicacion/comunicados/${id}/`, revision + refresh)
  const [updated, setUpdated] = useState<{ revision: number; row: Comunicado } | null>(null)
  const [confirm, setConfirm] = useState<'publish' | 'archive' | null>(null)
  const op = useOperation()
  const row = updated?.revision === revision ? updated.row : resource.data
  const canManage = manager && row?.puede_gestionar
  const locked = op.busy || op.denied
  function action(operation: () => Promise<{ data: Comunicado }>) {
    void op.run(async () => {
      const { data } = await operation()
      setUpdated({ revision: revision + 1, row: data })
    }, () => { setConfirm(null); onChanged() })
  }
  return <section aria-label="Detalle del comunicado" className="wf-card space-y-4">
    <div className="flex items-center justify-between gap-3"><h2>Detalle del comunicado</h2><button className="wf-secondary" disabled={op.busy} onClick={onClose}>Cerrar detalle</button></div>
    <Status loading={resource.loading && !row} error={resource.error} empty={false} />{resource.error && <button className="wf-secondary" onClick={() => setRefresh(v => v + 1)}>Reintentar detalle</button>}
    {!resource.error && row && <><h3 className="text-xl font-bold">{row.titulo}</h3><p className="text-sm font-semibold">{row.estado} · {row.prioridad === 'URGENTE' ? 'Urgente' : 'Normal'}</p><p className="whitespace-pre-wrap">{row.cuerpo}</p><p className="text-sm text-slate-600">{row.curso ? `Curso ${row.curso}` : 'Toda la unidad educativa'} · Unidad {row.unidad_educativa}</p>
      {row.requiere_confirmacion && <p className="text-sm text-slate-600">Se solicita confirmación de lectura.</p>}
      {row.leido_at && <p role="status" className="wf-success">Lectura confirmada el {fechaComunicacion(row.leido_at)}</p>}
      {canManage && row.estadisticas && <section aria-label="Estadísticas de lectura" className="rounded-xl bg-brand-50 p-4"><h3 className="font-semibold">Seguimiento de lectura</h3><p>{row.estadisticas.leidos} de {row.estadisticas.destinatarios} destinatarios · {row.estadisticas.porcentaje_lectura}% de lectura</p></section>}
      <Errors errors={op.errors} />
      <div className="flex flex-wrap gap-3">{canManage && row.estado === 'BORRADOR' && <><button className="wf-secondary" disabled={locked || Boolean(confirm)} onClick={() => onEdit(row)}>Editar borrador</button><button className="wf-primary" disabled={locked || Boolean(confirm)} onClick={() => setConfirm('publish')}>Publicar</button></>}{canManage && row.estado === 'PUBLICADO' && <button className="wf-secondary" disabled={locked || Boolean(confirm)} onClick={() => setConfirm('archive')}>Archivar</button>}{row.es_destinatario === true && row.estado === 'PUBLICADO' && !row.leido_at && <button className="wf-primary" disabled={locked} onClick={() => action(() => confirmarLectura(id))}>{op.busy ? 'Confirmando...' : 'Confirmar lectura'}</button>}</div>
      {confirm && <section aria-label={confirm === 'publish' ? 'Confirmar publicación' : 'Confirmar archivo'} className="rounded-xl border border-amber-300 bg-amber-50 p-4 space-y-3"><p>{confirm === 'publish' ? 'Se enviará a los destinatarios actuales de la audiencia elegida. Después de publicar no podrá editar el comunicado.' : 'El comunicado se archivará y conservará las confirmaciones de lectura.'}</p><div className="flex flex-wrap gap-3"><button className="wf-primary" disabled={locked} onClick={() => action(() => confirm === 'publish' ? publicarComunicado(id) : archivarComunicado(id))}>{op.busy ? 'Procesando...' : confirm === 'publish' ? 'Confirmar publicación' : 'Confirmar archivo'}</button><button className="wf-secondary" disabled={op.busy} onClick={() => setConfirm(null)}>Cancelar acción</button></div></section>}
    </>}
  </section>
}

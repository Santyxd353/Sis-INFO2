import axios from 'axios'
import { Eye, FilterX, Search, ShieldCheck, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import type { Colegio, UnidadEducativa } from '../../app/modelos/Institucion'
import type { Usuario } from '../../app/modelos/Usuarios'
import { listarAuditoria, obtenerEventoAuditoria, type EventoAuditoria, type FiltrosAuditoria } from '../../api/auditoria'
import { listarColegiosCatalogo, listarUnidadesCatalogo, listarUsuariosCatalogo } from '../../api/catalogosInstitucionales'

type Filtros = Omit<FiltrosAuditoria, 'usuario' | 'colegio' | 'unidad'> & { usuario: string; colegio: string; unidad: string }
const inicial: Filtros = { usuario: '', colegio: '', unidad: '', accion: '', entidad: '', desde: '', hasta: '', page: 1, page_size: 20 }
const positiveId = (value?: string) => { const parsed = Number(value); return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined }

export default function AuditoriaPage() {
  const auth = useAuth(), scope = auth.user?.alcance
  const global = auth.isSuperAdmin?.() || scope?.tipo === 'GLOBAL'
  const allowed = global || Boolean(auth.can?.('auditoria', 'listar') || auth.can?.('evento-auditoria', 'listar'))
  const fixedCollege = !global && scope?.tipo === 'COLEGIO' ? scope.colegio_id : undefined
  const fixedUnit = !global && scope?.tipo === 'UNIDAD' ? scope.unidad_id : undefined
  const [draft, setDraft] = useState(inicial), [applied, setApplied] = useState(inicial)
  const [events, setEvents] = useState<EventoAuditoria[]>([]), [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [detail, setDetail] = useState<EventoAuditoria | null>(null)
  const [colegios, setColegios] = useState<Colegio[]>([]), [unidades, setUnidades] = useState<UnidadEducativa[]>([]), [usuarios, setUsuarios] = useState<Usuario[]>([])
  const controller = useRef<AbortController | null>(null)
  const load = useCallback(async () => {
    if (!allowed) return
    controller.current?.abort(); const next = new AbortController(); controller.current = next; setLoading(true); setError('')
    try { const { data } = await listarAuditoria({ usuario: positiveId(applied.usuario), colegio: global ? positiveId(applied.colegio) : (fixedCollege ?? undefined), unidad: fixedUnit ?? positiveId(applied.unidad), accion: applied.accion, entidad: applied.entidad, desde: applied.desde, hasta: applied.hasta, page: applied.page, page_size: 20 }, next.signal); if (!next.signal.aborted) { setEvents(data.results); setTotal(data.count) } }
    catch (reason) { if (!next.signal.aborted) setError(axios.isAxiosError(reason) && reason.response?.status === 403 ? 'No tiene permiso para consultar la auditorÃ­a de este Ã¡mbito.' : 'No fue posible cargar la auditorÃ­a.') }
    finally { if (!next.signal.aborted) setLoading(false) }
  }, [allowed, applied, global, fixedCollege, fixedUnit])
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); return () => controller.current?.abort() }, [load])
  useEffect(() => { if (!allowed) return; void Promise.all([listarUsuariosCatalogo(), global ? listarColegiosCatalogo() : Promise.resolve([])]).then(([userList, schoolList]) => { setUsuarios(userList); setColegios(schoolList) }).catch(() => undefined) }, [allowed, global])
  const college = global ? positiveId(draft.colegio) : fixedCollege
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (!college) { setUnidades([]); return }; const controller = new AbortController(); void listarUnidadesCatalogo(college, controller.signal).then(setUnidades).catch(() => setUnidades([])); return () => controller.abort() }, [college])
  if (!allowed) return <section className="p-6"><h1 className="text-2xl font-bold">Seguridad y auditorÃ­a</h1><p role="alert" className="mt-4 text-red-700">No tiene permiso para consultar la auditorÃ­a.</p></section>
  const filteredUsers = usuarios.filter((user) => !college || user.colegio?.id === college || user.unidad?.colegio?.id === college)
  const actorLabel = (event: EventoAuditoria) => event.actor_username || event.actor_snapshot?.replace(/^usuario:/, '') || 'â€”'
  const apply = (event: React.FormEvent) => { event.preventDefault(); setApplied({ ...draft, page: 1 }) }
  return <section className="p-4 sm:p-6 lg:p-8" aria-labelledby="auditoria-titulo">
    <header className="mb-6"><div className="flex items-center gap-3"><ShieldCheck className="text-brand-700"/><h1 id="auditoria-titulo" className="text-2xl font-bold">Seguridad y auditorÃ­a</h1></div><p className="text-sm text-slate-500">Consulta inmutable de eventos institucionales.</p></header>
    <form className="mb-5 grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-4" onSubmit={apply}>
      {global ? <Select label="Colegio" value={draft.colegio} change={(colegio) => setDraft({ ...draft, colegio, unidad: '', usuario: '' })} options={colegios.map((item) => [String(item.id), item.nombre])} initial="Todos los colegios"/> : <Context label="Colegio" value={scope?.colegio_nombre ?? 'Colegio autorizado'}/>}
      {fixedUnit ? <Context label="Unidad educativa" value={scope?.unidad_nombre ?? 'Unidad autorizada'}/> : <Select label="Unidad educativa" value={draft.unidad} change={(unidad) => setDraft({ ...draft, unidad, usuario: '' })} options={unidades.map((item) => [String(item.id), item.nombre])} initial="Todas las unidades" disabled={!college}/>}
      <Select label="Usuario" value={draft.usuario} change={(usuario) => setDraft({ ...draft, usuario })} options={filteredUsers.map((item) => [String(item.id), `${item.nombre} ${item.apellido} (${item.username})`])} initial="Todos los usuarios"/>
      <Select label="AcciÃ³n" value={draft.accion ?? ''} change={(accion) => setDraft({ ...draft, accion })} options={['CREAR','ACTUALIZAR','DESACTIVAR','LOGIN_EXITOSO','LOGOUT'].map((item) => [item, item])} initial="Todas las acciones"/>
      <Select label="Entidad" value={draft.entidad ?? ''} change={(entidad) => setDraft({ ...draft, entidad })} options={['USUARIO','ASIGNACION_DOCENTE','AUTENTICACION','CURSO','ROL'].map((item) => [item, item])} initial="Todas las entidades"/>
      <Input label="Desde" type="date" value={draft.desde ?? ''} change={(desde) => setDraft({ ...draft, desde })}/><Input label="Hasta" type="date" value={draft.hasta ?? ''} change={(hasta) => setDraft({ ...draft, hasta })}/>
      <div className="flex gap-2 sm:col-span-2 lg:col-span-4"><button className="btn-primary" type="submit"><Search size={17}/>Filtrar</button><button className="btn-secondary" type="button" onClick={() => { setDraft(inicial); setApplied(inicial) }}><FilterX size={17}/>Limpiar filtros</button></div>
    </form>
    {error && <p role="alert" className="mb-3 text-red-700">{error} <button className="underline" onClick={() => void load()}>Reintentar</button></p>}<p className="mb-2 text-sm text-slate-500">Total: {total}</p>
    <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">{loading ? <p className="p-8 text-center">Cargando auditorÃ­a...</p> : events.length === 0 ? <p className="p-8 text-center">No se encontraron eventos.</p> : <table className="w-full text-left text-sm"><thead><tr>{['Fecha','Actor','Rol','AcciÃ³n','Entidad','Ãmbito','Detalle'].map((header) => <th key={header} className="px-4 py-3">{header}</th>)}</tr></thead><tbody>{events.map((event) => <tr key={event.id}><td className="px-4 py-3">{new Date(event.created_at).toLocaleString()}</td><td className="px-4 py-3">{actorLabel(event)}</td><td className="px-4 py-3">{event.actor_rol || 'â€”'}</td><td className="px-4 py-3">{event.accion}</td><td className="px-4 py-3">{event.entidad}</td><td className="px-4 py-3">{event.ambito}</td><td><button aria-label={`Ver evento ${event.id}`} onClick={() => void obtenerEventoAuditoria(event.id).then((response) => setDetail(response.data))}><Eye size={18}/></button></td></tr>)}</tbody></table>}</div>
    <Paginacion pagina={Number(applied.page)} paginas={Math.max(1, Math.ceil(total / 20))} total={total} cambiar={(page) => setApplied({ ...applied, page })}/>
    {detail && <div role="dialog" aria-modal="true"><button aria-label="Cerrar detalle" onClick={() => setDetail(null)}><X/></button><h2>Evento #{detail.id}</h2><pre>{JSON.stringify(detail.cambios_sanitizados ?? {}, null, 2)}</pre></div>}
  </section>
}
function Input({ label, value, change, type = 'text' }: { label: string; value: string; change: (value: string) => void; type?: string }) { const key = `auditoria-${label}`; return <label htmlFor={key}>{label}<input id={key} type={type} value={value} onChange={(event) => change(event.target.value)}/></label> }
function Select({ label, value, change, options, initial, disabled }: { label: string; value: string; change: (value: string) => void; options: string[][]; initial: string; disabled?: boolean }) { const key = `auditoria-${label}`; return <label htmlFor={key}>{label}<select id={key} value={value} disabled={disabled} onChange={(event) => change(event.target.value)}><option value="">{initial}</option>{options.map(([optionValue, text]) => <option key={optionValue} value={optionValue}>{text}</option>)}</select></label> }
function Context({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><p>{value}</p></div> }
export function Paginacion({ pagina, paginas, total, cambiar }: { pagina: number; paginas: number; total?: number; cambiar: (page: number) => void }) { return <div className="mt-4 flex gap-3"><button className="btn-secondary" disabled={pagina <= 1} onClick={() => cambiar(pagina - 1)}>Anterior</button><span>{total !== undefined ? `Total: ${total} Â· ` : ''}PÃ¡gina {pagina} de {paginas}</span><button className="btn-secondary" disabled={pagina >= paginas} onClick={() => cambiar(pagina + 1)}>Siguiente</button></div> }

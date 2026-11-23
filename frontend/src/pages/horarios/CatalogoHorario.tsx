import { useState, type ReactNode } from 'react'
import type { OpcionHorario } from '../../api/horarios'
import { usePaged } from '../workflows/useWorkflow'
import { Field, Pages } from '../workflows/WorkflowUI'

export default function CatalogoHorario<T extends OpcionHorario>({ label, endpoint, value, onChange, params = {}, disabled = false, required = false, error, emptyMessage }: {
  label: string
  endpoint: string
  value: T | null
  onChange: (value: T | null) => void
  params?: Record<string, string | number>
  disabled?: boolean
  required?: boolean
  error?: string
  emptyMessage?: ReactNode
}) {
  const [search, setSearch] = useState(''), [applied, setApplied] = useState(''), [page, setPage] = useState(1), [revision, setRevision] = useState(0)
  const data = usePaged<T>(endpoint, { ...params, search: applied, page }, revision, !disabled)
  return <div className="space-y-2 min-w-0">
    <div className="flex items-end gap-2"><div className="min-w-0 flex-1"><Field label={`Buscar ${label.replace(' *', '').toLocaleLowerCase()}`}><input aria-label={`Buscar ${label.replace(' *', '').toLocaleLowerCase()}`} className="wf-input" value={search} disabled={disabled} onChange={e => setSearch(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); setApplied(search); setPage(1) } }} /></Field></div><button type="button" aria-label={`Buscar opciones de ${label.replace(' *', '').toLocaleLowerCase()}`} className="wf-secondary" disabled={disabled} onClick={() => { setApplied(search); setPage(1) }}>Buscar</button></div>
    <Field label={label} error={error}><select aria-label={label} className="wf-input" required={required} disabled={disabled || data.loading || Boolean(data.error)} value={value?.id ?? ''} onChange={e => onChange(data.items.find(item => item.id === Number(e.target.value)) ?? null)}>
      <option value="">{required ? 'Seleccione una opción' : 'Todos'}</option>
      {value && !data.items.some(item => item.id === value.id) && <option value={value.id}>{value.nombre}</option>}
      {data.items.map(item => <option key={item.id} value={item.id}>{item.nombre}</option>)}
    </select></Field>
    {data.loading && <p role="status" className="text-sm text-slate-600">Cargando opciones de {label.replace(' *', '').toLocaleLowerCase()}...</p>}
    {data.error && <div role="alert" className="text-sm text-red-800">{data.error} <button type="button" className="wf-secondary" onClick={() => setRevision(v => v + 1)}>Reintentar catálogo</button></div>}
    {!disabled && !data.loading && !data.error && !data.items.length && <p className="text-sm text-slate-600">{emptyMessage ?? 'No se encontraron opciones. Cambie la búsqueda.'}</p>}
    {data.count > 20 && <div role="group" aria-label={`Páginas de ${label.replace(' *', '').toLocaleLowerCase()}`}><Pages page={page} count={data.count} onChange={setPage} /></div>}
  </div>
}

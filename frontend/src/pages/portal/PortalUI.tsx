import type { ReactNode } from 'react'
import type { GestionPortal, PeriodoPortal } from '../../api/portal'

export function PortalStatus({ loading, error, retry, title }: { loading: boolean; error: string | null; retry: () => void; title: string }) {
  return <>{loading && <p role="status" className="rounded-xl bg-white p-6 text-slate-600">Cargando {title}...</p>}{error && <div className="space-y-3"><p role="alert" className="rounded-xl bg-amber-50 p-4 text-amber-900">{error}</p><button type="button" className="btn-secondary" onClick={retry}>Reintentar</button></div>}</>
}
export function PortalSelect({ label, value, onChange, children, disabled = false }: { label: string; value: number | ''; onChange: (value: number | undefined) => void; children: ReactNode; disabled?: boolean }) {
  return <label className="flex min-w-0 flex-col gap-1.5 text-sm font-semibold text-slate-700">{label}<select className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal focus:outline-brand-700 disabled:opacity-60" value={value} disabled={disabled} onChange={event => onChange(event.target.value ? Number(event.target.value) : undefined)}>{children}</select></label>
}
export function CalendarFilters({ gestiones, gestion, periodos, periodo, onGestion, onPeriodo }: { gestiones: GestionPortal[]; gestion: number | ''; periodos: PeriodoPortal[]; periodo: number | ''; onGestion: (id?: number) => void; onPeriodo: (id?: number) => void }) {
  return <><PortalSelect label="Gestión académica" value={gestion} onChange={onGestion} disabled={!gestiones.length}>{!gestiones.length && <option value="">Sin gestiones</option>}{gestiones.map(row => <option key={row.id} value={row.id}>{row.anio}{row.activo ? ' · Activa' : ''}</option>)}</PortalSelect><PortalSelect label="Periodo académico" value={periodo} onChange={onPeriodo} disabled={!periodos.length}><option value="">Toda la gestión</option>{periodos.map(row => <option key={row.id} value={row.id}>{row.nombre}</option>)}</PortalSelect></>
}
export function PortalTable({ caption, columns, children }: { caption: string; columns: string[]; children: ReactNode }) {
  return <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><caption className="sr-only">{caption}</caption><thead className="bg-slate-50"><tr>{columns.map(column => <th key={column} scope="col" className="whitespace-nowrap px-4 py-3">{column}</th>)}</tr></thead><tbody className="divide-y divide-slate-100 [&_td]:px-4 [&_td]:py-3">{children}</tbody></table></div>
}
export function PortalMetric({ title, value, suffix = '' }: { title: string; value: number | null; suffix?: string }) {
  return <article aria-label={title} className="rounded-xl border border-slate-200 bg-white p-5"><h3 className="text-sm font-semibold text-slate-600">{title}</h3><p className="mt-2 text-3xl font-bold tabular-nums text-brand-900">{value === null ? <span className="text-lg text-slate-500">Sin datos</span> : `${value}${suffix}`}</p></article>
}
export function UpdatedAt({ date }: { date: string }) {
  return <p className="mt-6 text-xs text-slate-500">Actualizado: <time dateTime={date}>{new Date(date).toLocaleString('es-BO')}</time></p>
}

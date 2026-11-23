import { CreditCard } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import type { UnidadEducativa } from '../../app/modelos/Institucion'
import { listarUnidadesCatalogo } from '../../api/catalogosInstitucionales'
import { cargarCatalogoPaginado } from '../../api/catalogosPaginados'
import AlertasPagoTab from './AlertasPagoTab'
import BecasTab from './BecasTab'
import EstadoCuentaTab from './EstadoCuentaTab'
import MorosidadTab from './MorosidadTab'
import ObligacionesTab from './ObligacionesTab'
import PagosQRTab from './PagosQRTab'
import PagosTab from './PagosTab'
import PlanesPagoTab from './PlanesPagoTab'
import SimulacionTributariaTab from './SimulacionTributariaTab'
import { errorTexto, type ContextoFinanzas } from './utilidades'

type Tab = 'planes' | 'becas' | 'obligaciones' | 'pagos' | 'pagos-qr' | 'estado-cuenta' | 'morosidad' | 'alertas' | 'simulacion'

const CONTENIDO: Record<Tab, (props: { contexto: ContextoFinanzas }) => React.ReactElement> = {
  planes: PlanesPagoTab, becas: BecasTab, obligaciones: ObligacionesTab, pagos: PagosTab, 'pagos-qr': PagosQRTab,
  'estado-cuenta': EstadoCuentaTab, morosidad: MorosidadTab, alertas: AlertasPagoTab, simulacion: SimulacionTributariaTab,
}
interface Calendario { id: number; año: number; activo: boolean }

export default function FinanzasPage() {
  const { user, can } = useAuth()
  const alcance = user?.alcance
  const esDirector = alcance?.tipo === 'COLEGIO'
  const unidadFija = alcance?.tipo === 'UNIDAD' ? alcance.unidad_id : null
  const pestanas = ([
    ['planes', 'Planes de pago', can('plan-pago', 'listar')],
    ['becas', 'Becas', can('beca', 'listar')],
    ['obligaciones', 'Obligaciones', can('obligacion-pago', 'listar')],
    ['pagos', 'Pagos', can('pago', 'listar')],
    ['pagos-qr', 'Pagos QR', can('pago-qr', 'listar')],
    ['estado-cuenta', 'Estado de cuenta', can('estado-cuenta', 'listar')],
    ['morosidad', 'Morosidad', can('morosidad', 'listar')],
    ['alertas', 'Alertas de pago', can('alerta-pago', 'listar')],
    ['simulacion', 'Simulación tributaria', can('simulacion-tributaria', 'listar')],
  ] as [Tab, string, boolean][]).filter(([, , visible]) => visible)
  const [tab, setTab] = useState<Tab | undefined>(pestanas[0]?.[0])
  const [unidades, setUnidades] = useState<UnidadEducativa[]>([])
  const [unidad, setUnidad] = useState(unidadFija ? String(unidadFija) : '')
  const [calendarios, setCalendarios] = useState<Calendario[]>([])
  const [calendario, setCalendario] = useState('')
  const [error, setError] = useState('')
  const unidadId = Number(unidad) || undefined

  useEffect(() => {
    if (!esDirector || !alcance?.colegio_id) return
    const controller = new AbortController()
    listarUnidadesCatalogo(alcance.colegio_id, controller.signal)
      .then(data => { if (!controller.signal.aborted) setUnidades(data) })
      .catch(e => { if (!controller.signal.aborted) setError(errorTexto(e, 'No fue posible cargar las unidades educativas.')) })
    return () => controller.abort()
  }, [alcance?.colegio_id, esDirector])

  useEffect(() => {
    if (!unidadId) return
    const controller = new AbortController()
    cargarCatalogoPaginado<Calendario>('/calendario/calendarios/', { unidad_educativa: unidadId }, controller.signal)
      .then(data => {
        if (controller.signal.aborted) return
        const ordenados = [...data].sort((a, b) => b.año - a.año)
        setCalendarios(ordenados)
        setCalendario(String((ordenados.find(c => c.activo) ?? ordenados[0])?.id ?? ''))
      })
      .catch(e => { if (!controller.signal.aborted) setError(errorTexto(e, 'No fue posible cargar las gestiones.')) })
    return () => controller.abort()
  }, [unidadId])

  if (!tab) return <section className="p-6"><h1 className="text-2xl font-bold">Pensiones y pagos</h1><p role="alert" className="mt-4 rounded-xl bg-red-50 p-4 text-red-700">No tiene permisos para realizar esta acción.</p></section>

  const cambiarUnidad = (valor: string) => { setUnidad(valor); setCalendarios([]); setCalendario('') }
  const contexto = unidadId ? { unidadId, calendarioId: Number(calendario) || undefined } : null
  const Contenido = CONTENIDO[tab]

  return <section className="space-y-6 p-4 sm:p-6 lg:p-8" aria-labelledby="finanzas-title">
    <header className="flex flex-wrap items-center gap-3"><CreditCard className="text-brand-700" /><div><h1 id="finanzas-title" className="text-2xl font-bold">Pensiones y pagos</h1><p className="text-sm text-slate-500">Planes de pago por gestión, becas y obligaciones de los estudiantes.</p></div></header>
    <div className="grid gap-3 rounded-2xl bg-white p-4 shadow-sm md:grid-cols-3">
      <label className="text-sm font-medium">Unidad educativa
        {esDirector ? <select aria-label="Unidad educativa" value={unidad} onChange={e => cambiarUnidad(e.target.value)} className="mt-1 w-full rounded-lg border p-2"><option value="">Seleccione una unidad</option>{unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}</select>
          : <p className="mt-1 rounded-lg border p-2">{alcance?.unidad_nombre ?? 'Unidad asignada'}</p>}
      </label>
      <label className="text-sm font-medium">Gestión
        <select aria-label="Gestión" value={calendario} disabled={!unidadId} onChange={e => setCalendario(e.target.value)} className="mt-1 w-full rounded-lg border p-2">
          <option value="">{unidadId && calendarios.length === 0 ? 'Sin gestiones registradas' : 'Seleccione una gestión'}</option>
          {calendarios.map(c => <option key={c.id} value={c.id}>{c.año}{c.activo ? ' (activa)' : ''}</option>)}
        </select>
      </label>
    </div>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}
    <div className="flex gap-2 overflow-x-auto border-b" role="tablist">
      {pestanas.map(([clave, titulo]) => <button key={clave} role="tab" aria-selected={tab === clave} className={tab === clave ? 'whitespace-nowrap border-b-2 border-brand-700 px-3 py-2 font-semibold text-brand-700' : 'whitespace-nowrap px-3 py-2'} onClick={() => setTab(clave)}>{titulo}</button>)}
    </div>
    {!contexto ? <p className="rounded-xl bg-amber-50 p-4 text-amber-800">Seleccione una unidad educativa.</p>
      : <Contenido key={`${tab}-${contexto.unidadId}`} contexto={contexto} />}
  </section>
}

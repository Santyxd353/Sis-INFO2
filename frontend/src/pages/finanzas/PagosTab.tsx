import axios from 'axios'
import { Ban, FileDown, Plus } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import {
  abrirRecibo, anularPago, formatoMonto, listarObligaciones, listarPagos, METODOS_PAGO, registrarPago,
  type EstudianteElegible, type MetodoPago, type ObligacionPago, type Pago,
} from '../../api/finanzas'
import { Paginacion } from '../auditoria/AuditoriaPage'
import { Avisos, BuscadorEstudiante, Campo, Estado, Modal, Tabla } from './comunes'
import { errorTexto, PAGE_SIZE, type ContextoFinanzas } from './utilidades'

const hoy = () => new Date().toLocaleDateString('en-CA')

export default function PagosTab({ contexto }: { contexto: ContextoFinanzas }) {
  const { can } = useAuth()
  const { unidadId } = contexto
  const [pagos, setPagos] = useState<Pago[]>([])
  const [total, setTotal] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [estado, setEstado] = useState('')
  const [metodo, setMetodo] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [registrando, setRegistrando] = useState(false)
  const consulta = useRef<AbortController | null>(null)

  const cargar = useCallback(async () => {
    consulta.current?.abort(); const controller = new AbortController(); consulta.current = controller
    setCargando(true); setError('')
    try {
      const { data } = await listarPagos({ unidad_educativa: unidadId, estado, metodo, desde, hasta, page: pagina, page_size: PAGE_SIZE }, controller.signal)
      if (!controller.signal.aborted) { setPagos(data.results); setTotal(data.count) }
    } catch (e) { if (!controller.signal.aborted && !axios.isCancel(e)) setError(errorTexto(e, 'No fue posible cargar los pagos.')) }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }, [unidadId, estado, metodo, desde, hasta, pagina])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar(); return () => consulta.current?.abort() }, [cargar])

  const anular = async (pago: Pago) => {
    const motivo = window.prompt(`Motivo para anular el recibo N.º ${pago.numero_recibo}:`)
    if (!motivo?.trim()) return
    setError(''); setExito('')
    try { await anularPago(pago.id, motivo.trim()); setExito(`Recibo ${pago.numero_recibo} anulado; las cuotas recuperaron su saldo.`); await cargar() }
    catch (e) { setError(errorTexto(e, 'No fue posible anular el pago.')) }
  }
  const descargar = async (pago: Pago) => {
    try { await abrirRecibo(pago) } catch (e) { setError(errorTexto(e, 'No fue posible descargar el recibo.')) }
  }
  const filtrar = (cambio: () => void) => { cambio(); setPagina(1) }

  const puedeRegistrar = can('pago', 'crear'), puedeAnular = can('pago', 'anular')
  return <div className="space-y-4">
    <div className="grid gap-3 rounded-2xl bg-white p-4 shadow-sm md:grid-cols-5">
      <Campo label="Estado"><select aria-label="Estado del pago" value={estado} onChange={e => filtrar(() => setEstado(e.target.value))} className="w-full rounded-lg border p-2"><option value="">Todos</option><option value="VALIDO">Válido</option><option value="ANULADO">Anulado</option></select></Campo>
      <Campo label="Método"><select aria-label="Método de pago" value={metodo} onChange={e => filtrar(() => setMetodo(e.target.value))} className="w-full rounded-lg border p-2"><option value="">Todos</option>{METODOS_PAGO.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></Campo>
      <Campo label="Desde"><input aria-label="Desde" type="date" value={desde} onChange={e => filtrar(() => setDesde(e.target.value))} className="w-full rounded-lg border p-2" /></Campo>
      <Campo label="Hasta"><input aria-label="Hasta" type="date" value={hasta} onChange={e => filtrar(() => setHasta(e.target.value))} className="w-full rounded-lg border p-2" /></Campo>
      <div className="flex items-end justify-end">{puedeRegistrar && <button className="btn-primary" onClick={() => { setExito(''); setRegistrando(true) }}><Plus size={17} />Registrar pago</button>}</div>
    </div>
    <Avisos error={error} exito={exito} reintentar={() => void cargar()} />
    <Tabla columnas={['Recibo', 'Fecha', 'Estudiante', 'Conceptos', 'Método', 'Monto', 'Estado', 'Acciones']} cargando={cargando} vacio={pagos.length === 0}>
      {pagos.map(p => <tr key={p.id} className="border-t">
        <td className="p-4 font-mono">{String(p.numero_recibo).padStart(6, '0')}</td>
        <td className="p-4">{p.fecha_pago}</td>
        <td className="p-4 font-medium">{p.estudiante_nombre}<p className="text-xs font-normal text-slate-500">{p.curso_nombre ?? ''}</p></td>
        <td className="p-4 text-xs">{p.detalles.map(d => d.concepto).join(', ')}</td>
        <td className="p-4">{p.metodo_display}{p.referencia && <p className="text-xs text-slate-500">Ref. {p.referencia}</p>}</td>
        <td className="p-4 font-semibold">{formatoMonto(p.monto)}</td>
        <td className="p-4"><Estado valor={p.estado} />{p.motivo_anulacion && <p className="mt-1 text-xs text-slate-500">{p.motivo_anulacion}</p>}</td>
        <td className="p-4"><div className="flex gap-3">
          <button aria-label={`Descargar recibo ${p.numero_recibo}`} title="Descargar recibo" onClick={() => void descargar(p)}><FileDown size={18} /></button>
          {puedeAnular && p.estado === 'VALIDO' && <button aria-label={`Anular recibo ${p.numero_recibo}`} title="Anular" className="text-red-600" onClick={() => void anular(p)}><Ban size={18} /></button>}
        </div></td>
      </tr>)}
    </Tabla>
    <Paginacion pagina={pagina} paginas={Math.max(1, Math.ceil(total / PAGE_SIZE))} cambiar={setPagina} />
    {registrando && <RegistrarPago unidadId={unidadId} cerrar={() => setRegistrando(false)} alRegistrar={pago => { setExito(`Pago registrado con recibo N.º ${pago.numero_recibo}.`); void cargar() }} />}
  </div>
}

function RegistrarPago({ unidadId, cerrar, alRegistrar }: { unidadId: number; cerrar: () => void; alRegistrar: (pago: Pago) => void }) {
  const [estudiante, setEstudiante] = useState<EstudianteElegible | null>(null)
  const [pendientes, setPendientes] = useState<ObligacionPago[]>([])
  const [seleccion, setSeleccion] = useState<number[]>([])
  const [monto, setMonto] = useState('')
  const [metodo, setMetodo] = useState<MetodoPago>('EFECTIVO')
  const [fecha, setFecha] = useState(hoy())
  const [referencia, setReferencia] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [registrado, setRegistrado] = useState<Pago | null>(null)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const saldoDe = (ids: number[]) => pendientes.filter(o => ids.includes(o.id)).reduce((s, o) => s + Number(o.saldo), 0)
  const elegir = async (nuevo: EstudianteElegible | null) => {
    setEstudiante(nuevo); setPendientes([]); setSeleccion([]); setMonto(''); setError('')
    if (!nuevo) return
    try {
      const { data } = await listarObligaciones({ estudiante: nuevo.id, estado: 'PENDIENTE', page_size: 100 })
      const conSaldo = data.results.filter(o => Number(o.saldo) > 0)
      setPendientes(conSaldo)
      if (conSaldo.length === 0) setError('El estudiante no tiene cuotas pendientes.')
    } catch (e) { setError(errorTexto(e, 'No fue posible cargar las cuotas pendientes.')) }
  }
  const alternar = (id: number) => {
    const nueva = seleccion.includes(id) ? seleccion.filter(x => x !== id) : [...seleccion, id]
    setSeleccion(nueva); setMonto(nueva.length ? saldoDe(nueva).toFixed(2) : '')
  }
  const guardar = async () => {
    if (!estudiante || !(Number(monto) > 0)) { setError('Seleccione el estudiante y un monto mayor a cero.'); return }
    if (seleccion.length && Number(monto) > saldoDe(seleccion) + 0.001) { setError('El monto supera el saldo de las cuotas seleccionadas.'); return }
    if ((metodo === 'TRANSFERENCIA' || metodo === 'QR') && !referencia.trim()) { setError('Indique el número de operación.'); return }
    setEnviando(true); setError('')
    try {
      const { data } = await registrarPago({
        estudiante: estudiante.id, monto, metodo, fecha_pago: fecha, referencia: referencia.trim(),
        observaciones: observaciones.trim(), obligaciones: seleccion.length ? seleccion : undefined,
      })
      setRegistrado(data); alRegistrar(data)
    } catch (e) { setError(errorTexto(e, 'No fue posible registrar el pago.')) }
    finally { setEnviando(false) }
  }

  if (registrado) return <Modal title="Pago registrado" close={cerrar}>
    <p role="status" className="rounded-lg bg-emerald-50 p-3 text-emerald-800">Recibo N.º {String(registrado.numero_recibo).padStart(6, '0')} por {formatoMonto(registrado.monto)} a nombre de {registrado.estudiante_nombre}.</p>
    <ul className="mt-3 text-sm">{registrado.detalles.map(d => <li key={d.id}>{d.concepto}: {formatoMonto(d.monto)}</li>)}</ul>
    <div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={cerrar}>Cerrar</button><button className="btn-primary" onClick={() => void abrirRecibo(registrado).catch(e => setError(errorTexto(e, 'No fue posible descargar el recibo.')))}><FileDown size={17} />Descargar recibo</button></div>
    <Avisos error={error} exito="" />
  </Modal>

  return <Modal title="Registrar pago" close={cerrar} ancho="max-w-2xl">
    <div className="space-y-3">
      <div className="text-sm font-medium">Estudiante<div className="mt-1"><BuscadorEstudiante unidadId={unidadId} seleccionado={estudiante} onSeleccionar={nuevo => void elegir(nuevo)} /></div></div>
      {pendientes.length > 0 && <div>
        <p className="text-sm font-medium">Cuotas pendientes <span className="font-normal text-slate-500">(sin seleccionar, el pago se aplica a las más antiguas)</span></p>
        <ul className="mt-1 max-h-56 divide-y overflow-y-auto rounded-lg border">
          {pendientes.map(o => <li key={o.id}><label className="flex items-center gap-3 p-2 text-sm">
            <input type="checkbox" aria-label={`Seleccionar ${o.concepto}`} checked={seleccion.includes(o.id)} onChange={() => alternar(o.id)} />
            <span className="flex-1">{o.concepto} <span className="text-xs text-slate-500">· vence {o.fecha_vencimiento}</span>{o.vencida && <span className="ml-2 text-xs font-semibold text-red-600">Vencida</span>}</span>
            <span className="font-semibold">{formatoMonto(o.saldo)}</span>
          </label></li>)}
        </ul>
        <p className="mt-1 text-right text-sm text-slate-600">Saldo total: {formatoMonto(saldoDe(pendientes.map(o => o.id)))}</p>
      </div>}
      <div className="grid grid-cols-2 gap-3">
        <Campo label="Monto (Bs)"><input aria-label="Monto del pago" type="number" min="0.01" step="0.01" value={monto} onChange={e => setMonto(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>
        <Campo label="Fecha de pago"><input aria-label="Fecha de pago" type="date" max={hoy()} value={fecha} onChange={e => setFecha(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>
        <Campo label="Método"><select aria-label="Método" value={metodo} onChange={e => setMetodo(e.target.value as MetodoPago)} className="w-full rounded-lg border p-2">{METODOS_PAGO.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></Campo>
        <Campo label={metodo === 'EFECTIVO' ? 'Referencia (opcional)' : 'N.º de operación'}><input aria-label="Referencia" value={referencia} onChange={e => setReferencia(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>
      </div>
      <Campo label="Observaciones"><textarea aria-label="Observaciones" value={observaciones} onChange={e => setObservaciones(e.target.value)} className="w-full rounded-lg border p-2" rows={2} /></Campo>
    </div>
    <Avisos error={error} exito="" />
    <div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={cerrar}>Cancelar</button><button className="btn-primary" disabled={enviando || !estudiante || pendientes.length === 0} onClick={() => void guardar()}>{enviando ? 'Registrando...' : 'Registrar pago'}</button></div>
  </Modal>
}

import axios from 'axios'
import { Ban } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import { cargarCatalogoPaginado } from '../../api/catalogosPaginados'
import { anularObligacion, formatoMonto, listarObligaciones, type ObligacionPago } from '../../api/finanzas'
import { Paginacion } from '../auditoria/AuditoriaPage'
import { Avisos, Campo, Estado, Tabla } from './comunes'
import { errorTexto, PAGE_SIZE, type ContextoFinanzas } from './utilidades'

export default function ObligacionesTab({ contexto }: { contexto: ContextoFinanzas }) {
  const { can } = useAuth()
  const { unidadId, calendarioId } = contexto
  const [obligaciones, setObligaciones] = useState<ObligacionPago[]>([])
  const [total, setTotal] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [curso, setCurso] = useState('')
  const [estado, setEstado] = useState('PENDIENTE')
  const [soloVencidas, setSoloVencidas] = useState(false)
  const [cursos, setCursos] = useState<{ id: number; nombre: string }[]>([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const consulta = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    cargarCatalogoPaginado<{ id: number; nombre: string }>('/academico/cursos/', { unidad_educativa: unidadId }, controller.signal)
      .then(data => { if (!controller.signal.aborted) setCursos(data) })
      .catch(e => { if (!controller.signal.aborted) setError(errorTexto(e, 'No fue posible cargar los cursos.')) })
    return () => controller.abort()
  }, [unidadId])

  const cargar = useCallback(async () => {
    if (!calendarioId) { setObligaciones([]); setTotal(0); return }
    consulta.current?.abort(); const controller = new AbortController(); consulta.current = controller
    setCargando(true); setError('')
    try {
      const { data } = await listarObligaciones({
        unidad_educativa: unidadId, calendario_academico: calendarioId, curso: curso || undefined,
        estado: soloVencidas ? undefined : estado, vencidas: soloVencidas || undefined, page: pagina, page_size: PAGE_SIZE,
      }, controller.signal)
      if (!controller.signal.aborted) { setObligaciones(data.results); setTotal(data.count) }
    } catch (e) { if (!controller.signal.aborted && !axios.isCancel(e)) setError(errorTexto(e, 'No fue posible cargar las obligaciones.')) }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }, [unidadId, calendarioId, curso, estado, soloVencidas, pagina])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar(); return () => consulta.current?.abort() }, [cargar])

  const anular = async (obligacion: ObligacionPago) => {
    const motivo = window.prompt(`Motivo para anular "${obligacion.concepto}" de ${obligacion.estudiante_nombre}:`)
    if (!motivo?.trim()) return
    setError(''); setExito('')
    try { await anularObligacion(obligacion.id, motivo.trim()); setExito('Obligación anulada.'); await cargar() }
    catch (e) { setError(errorTexto(e, 'No fue posible anular la obligación.')) }
  }

  if (!calendarioId) return <p className="rounded-xl bg-amber-50 p-4 text-amber-800">Seleccione una gestión para ver las obligaciones.</p>
  const puedeAnular = can('obligacion-pago', 'editar')
  const sumaPagina = obligaciones.filter(o => o.estado === 'PENDIENTE').reduce((suma, o) => suma + Number(o.saldo), 0)

  return <div className="space-y-4">
    <div className="grid gap-3 rounded-2xl bg-white p-4 shadow-sm md:grid-cols-4">
      <Campo label="Curso"><select aria-label="Curso" value={curso} onChange={e => { setCurso(e.target.value); setPagina(1) }} className="w-full rounded-lg border p-2"><option value="">Todos</option>{cursos.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></Campo>
      <Campo label="Estado"><select aria-label="Estado de la obligación" disabled={soloVencidas} value={estado} onChange={e => { setEstado(e.target.value); setPagina(1) }} className="w-full rounded-lg border p-2"><option value="">Todos</option><option value="PENDIENTE">Pendiente</option><option value="PAGADA">Pagada</option><option value="ANULADA">Anulada</option></select></Campo>
      <label className="flex items-center gap-2 self-end pb-2 text-sm font-medium"><input type="checkbox" checked={soloVencidas} onChange={e => { setSoloVencidas(e.target.checked); setPagina(1) }} />Solo vencidas</label>
      <div className="self-end pb-2 text-right text-sm text-slate-600">{total} registro(s){sumaPagina > 0 && <> · pendiente en página: <strong>{formatoMonto(sumaPagina)}</strong></>}</div>
    </div>
    <Avisos error={error} exito={exito} reintentar={() => void cargar()} />
    <Tabla columnas={['Estudiante', 'Curso', 'Concepto', 'Vence', 'Monto', 'Descuento', 'Saldo', 'Estado', ...(puedeAnular ? ['Acciones'] : [])]} cargando={cargando} vacio={obligaciones.length === 0}>
      {obligaciones.map(o => <tr key={o.id} className="border-t">
        <td className="p-4 font-medium">{o.estudiante_nombre}</td>
        <td className="p-4">{o.curso_nombre ?? '—'}</td>
        <td className="p-4">{o.concepto}<p className="text-xs text-slate-500">{o.plan_nombre}</p></td>
        <td className="p-4">{o.fecha_vencimiento}</td>
        <td className="p-4">{formatoMonto(o.monto_original)}</td>
        <td className="p-4">{Number(o.descuento) > 0 ? <>{formatoMonto(o.descuento)}<p className="text-xs text-emerald-700">{o.beca_nombre}</p></> : '—'}</td>
        <td className="p-4 font-semibold">{formatoMonto(o.saldo)}{Number(o.monto_pagado) > 0 && <p className="text-xs font-normal text-emerald-700">Pagado {formatoMonto(o.monto_pagado)}</p>}</td>
        <td className="p-4"><Estado valor={o.vencida ? 'VENCIDA' : o.estado} /></td>
        {puedeAnular && <td className="p-4">{o.estado === 'PENDIENTE' && <button aria-label={`Anular ${o.concepto} de ${o.estudiante_nombre}`} title="Anular" className="text-red-600" onClick={() => void anular(o)}><Ban size={18} /></button>}</td>}
      </tr>)}
    </Tabla>
    <Paginacion pagina={pagina} paginas={Math.max(1, Math.ceil(total / PAGE_SIZE))} cambiar={setPagina} />
  </div>
}

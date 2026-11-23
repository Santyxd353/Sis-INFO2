import axios from 'axios'
import { Ban, QrCode, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import {
  anularSolicitudQR, crearSolicitudQR, formatoMonto, listarObligaciones, listarSolicitudesQR, obtenerConciliacionQR,
  resolverSolicitudQR, simularCobroQR, verificarSolicitudQR,
  type ConciliacionQR, type EstudianteElegible, type ObligacionPago, type SolicitudQR,
} from '../../api/finanzas'
import { Paginacion } from '../auditoria/AuditoriaPage'
import { Avisos, BuscadorEstudiante, Campo, Estado, Modal, Tabla, Tarjeta } from './comunes'
import { errorTexto, PAGE_SIZE, type ContextoFinanzas } from './utilidades'

const hora = (iso: string) => new Date(iso).toLocaleString('es-BO', { dateStyle: 'short', timeStyle: 'short' })

export default function PagosQRTab({ contexto }: { contexto: ContextoFinanzas }) {
  const { can } = useAuth()
  const { unidadId } = contexto
  const [solicitudes, setSolicitudes] = useState<SolicitudQR[]>([])
  const [total, setTotal] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [estado, setEstado] = useState('')
  const [conciliacion, setConciliacion] = useState<ConciliacionQR | null>(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [abierta, setAbierta] = useState<SolicitudQR | 'nueva' | null>(null)
  const consulta = useRef<AbortController | null>(null)
  const puedeConciliar = can('pago-qr', 'conciliar')

  const cargar = useCallback(async () => {
    consulta.current?.abort(); const controller = new AbortController(); consulta.current = controller
    setCargando(true); setError('')
    try {
      const [lista, cuadre] = await Promise.all([
        listarSolicitudesQR({ unidad_educativa: unidadId, estado, page: pagina, page_size: PAGE_SIZE }, controller.signal),
        puedeConciliar ? obtenerConciliacionQR({ unidad_educativa: unidadId }, controller.signal) : Promise.resolve(null),
      ])
      if (controller.signal.aborted) return
      setSolicitudes(lista.data.results); setTotal(lista.data.count); setConciliacion(cuadre?.data ?? null)
    } catch (e) { if (!controller.signal.aborted && !axios.isCancel(e)) setError(errorTexto(e, 'No fue posible cargar los pagos QR.')) }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }, [unidadId, estado, pagina, puedeConciliar])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar(); return () => consulta.current?.abort() }, [cargar])

  const ejecutar = async (accion: () => Promise<unknown>, mensaje: string) => {
    setError(''); setExito('')
    try { await accion(); setExito(mensaje); await cargar() }
    catch (e) { setError(errorTexto(e, 'No fue posible completar la operación.')) }
  }
  const resolver = (solicitud: SolicitudQR, accion: 'aplicar' | 'descartar') => {
    const motivo = window.prompt(accion === 'aplicar'
      ? `Se registrará un pago de ${formatoMonto(solicitud.monto_reportado ?? 0)} a las cuotas más antiguas de ${solicitud.estudiante_nombre}. Motivo:`
      : `El QR de ${solicitud.estudiante_nombre} quedará anulado sin registrar pago. Motivo:`)
    if (motivo?.trim()) void ejecutar(() => resolverSolicitudQR(solicitud.id, accion, motivo.trim()), 'Solicitud conciliada.')
  }
  const anular = (solicitud: SolicitudQR) => {
    const motivo = window.prompt(`Motivo para anular el QR de ${solicitud.estudiante_nombre}:`)
    if (motivo?.trim()) void ejecutar(() => anularSolicitudQR(solicitud.id, motivo.trim()), 'QR anulado.')
  }

  const r = conciliacion?.resumen
  return <div className="space-y-4">
    {conciliacion?.modo_simulado && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">El <strong>modo simulado</strong> está habilitado. Las solicitudes de prueba se identifican con la etiqueta «QR simulado».</p>}
    {r && <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Tarjeta titulo="Cobrado según pasarela" valor={formatoMonto(r.cobrado_pasarela)} />
      <Tarjeta titulo="Registrado en el sistema" valor={formatoMonto(r.registrado_sistema)} tono="emerald" detalle={`${r.conciliadas} QR conciliados`} />
      <Tarjeta titulo="Diferencia por conciliar" valor={formatoMonto(r.diferencia)} tono={Number(r.diferencia) !== 0 ? 'red' : 'slate'} detalle={`${r.observadas} observados · ${r.descuadres} descuadres`} />
      <Tarjeta titulo="Pagos QR sin respaldo" valor={r.pagos_qr_sin_respaldo} tono={r.pagos_qr_sin_respaldo ? 'amber' : 'slate'} detalle={`Registrados a mano: ${formatoMonto(r.monto_qr_sin_respaldo)}`} />
    </div>}
    {conciliacion && conciliacion.por_resolver.length > 0 && <section className="space-y-2">
      <h2 className="text-lg font-semibold">Por conciliar</h2>
      <Tabla columnas={['Estudiante', 'QR emitido', 'Cobrado', 'Situación', 'Detalle', 'Acciones']} cargando={false} vacio={false}>
        {conciliacion.por_resolver.map(s => <tr key={s.id} className="border-t">
          <td className="p-4 font-medium">{s.estudiante_nombre}</td>
          <td className="p-4">{formatoMonto(s.monto)}</td>
          <td className="p-4">{s.monto_reportado ? formatoMonto(s.monto_reportado) : '—'}</td>
          <td className="p-4"><Estado valor={s.conciliacion} />{s.simulado && <p className="mt-1 text-xs font-medium text-amber-800">QR simulado</p>}</td>
          <td className="p-4 text-xs">{s.conciliacion === 'DESCUADRE' ? `El recibo ${s.numero_recibo} fue anulado, pero la pasarela sí cobró.` : s.observacion}</td>
          <td className="p-4">{s.estado === 'OBSERVADA' && <div className="flex flex-wrap gap-2">
            {s.monto_reportado && <button className="btn-secondary" onClick={() => resolver(s, 'aplicar')}>Aplicar cobro</button>}
            <button className="btn-secondary text-red-700" onClick={() => resolver(s, 'descartar')}>Descartar</button>
          </div>}</td>
        </tr>)}
      </Tabla>
    </section>}

    <div className="flex flex-wrap items-end justify-between gap-3">
      <Campo label="Estado del QR"><select aria-label="Estado del QR" value={estado} onChange={e => { setEstado(e.target.value); setPagina(1) }} className="w-48 rounded-lg border p-2">
        <option value="">Todos</option><option value="PENDIENTE">Pendiente</option><option value="PAGADA">Pagada</option><option value="OBSERVADA">Observada</option><option value="EXPIRADA">Expirada</option><option value="ANULADA">Anulada</option>
      </select></Campo>
      {can('pago-qr', 'crear') && <button className="btn-primary" onClick={() => { setExito(''); setAbierta('nueva') }}><QrCode size={17} />Generar QR</button>}
    </div>
    <Avisos error={abierta ? '' : error} exito={exito} reintentar={() => void cargar()} />
    <Tabla columnas={['Fecha', 'Estudiante', 'Cuotas', 'Monto', 'Estado', 'Recibo', 'Acciones']} cargando={cargando} vacio={solicitudes.length === 0}>
      {solicitudes.map(s => <tr key={s.id} className="border-t">
        <td className="p-4">{hora(s.created_at)}<p className="text-xs text-slate-500">{s.solicitado_por_nombre}</p></td>
        <td className="p-4 font-medium">{s.estudiante_nombre}<p className="text-xs font-normal text-slate-500">{s.curso_nombre ?? ''}</p></td>
        <td className="p-4 text-xs">{s.conceptos.join(', ')}</td>
        <td className="p-4 font-semibold">{formatoMonto(s.monto)}</td>
        <td className="p-4"><Estado valor={s.conciliacion} />{s.simulado && <p className="mt-1 text-xs font-medium text-amber-800">QR simulado</p>}</td>
        <td className="p-4 font-mono">{s.numero_recibo ? String(s.numero_recibo).padStart(6, '0') : '—'}</td>
        <td className="p-4">{s.estado === 'PENDIENTE' && <div className="flex gap-3">
          <button aria-label={`Ver QR de ${s.estudiante_nombre}`} title="Ver QR" onClick={() => setAbierta(s)}><QrCode size={18} /></button>
          <button aria-label={`Verificar QR de ${s.estudiante_nombre}`} title="Verificar pago" onClick={() => void ejecutar(() => verificarSolicitudQR(s.id), 'Estado actualizado con la pasarela.')}><RefreshCw size={18} /></button>
          <button aria-label={`Anular QR de ${s.estudiante_nombre}`} title="Anular" className="text-red-600" onClick={() => anular(s)}><Ban size={18} /></button>
        </div>}</td>
      </tr>)}
    </Tabla>
    <Paginacion pagina={pagina} paginas={Math.max(1, Math.ceil(total / PAGE_SIZE))} cambiar={setPagina} />
    {abierta && <DialogoQR unidadId={unidadId} inicial={abierta === 'nueva' ? null : abierta} puedeSimular={puedeConciliar}
      cerrar={() => { setAbierta(null); void cargar() }} />}
  </div>
}

function DialogoQR({ unidadId, inicial, puedeSimular, cerrar }: { unidadId: number; inicial: SolicitudQR | null; puedeSimular: boolean; cerrar: () => void }) {
  const [solicitud, setSolicitud] = useState<SolicitudQR | null>(inicial)
  const [estudiante, setEstudiante] = useState<EstudianteElegible | null>(null)
  const [pendientes, setPendientes] = useState<ObligacionPago[]>([])
  const [seleccion, setSeleccion] = useState<number[]>([])
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const elegir = async (nuevo: EstudianteElegible | null) => {
    setEstudiante(nuevo); setPendientes([]); setSeleccion([]); setError('')
    if (!nuevo) return
    try {
      const { data } = await listarObligaciones({ estudiante: nuevo.id, estado: 'PENDIENTE', page_size: 100 })
      const conSaldo = data.results.filter(o => Number(o.saldo) > 0)
      setPendientes(conSaldo); setSeleccion(conSaldo.filter(o => o.vencida).map(o => o.id))
      if (conSaldo.length === 0) setError('El estudiante no tiene cuotas pendientes.')
    } catch (e) { setError(errorTexto(e, 'No fue posible cargar las cuotas pendientes.')) }
  }
  const accion = async (operacion: () => Promise<{ data: SolicitudQR }>) => {
    setEnviando(true); setError('')
    try { setSolicitud((await operacion()).data) }
    catch (e) { setError(errorTexto(e, 'No fue posible completar la operación.')) }
    finally { setEnviando(false) }
  }
  const totalSeleccion = pendientes.filter(o => seleccion.includes(o.id)).reduce((s, o) => s + Number(o.saldo), 0)

  if (solicitud) return <Modal title={`Pago QR · ${solicitud.estudiante_nombre}`} close={cerrar}>
    {solicitud.simulado && <p className="mb-3 rounded-lg bg-amber-50 p-3 text-sm font-medium text-amber-800">QR simulado de demostración</p>}
    {solicitud.estado === 'PENDIENTE' ? <div className="text-center">
      <img src={solicitud.qr_url} alt={solicitud.simulado ? 'Código QR simulado' : 'Código QR de pago'} className="mx-auto h-56 w-56 rounded-lg border" />
      <p className="mt-3 text-2xl font-bold">{formatoMonto(solicitud.monto)}</p>
      <p className="text-sm text-slate-500">{solicitud.conceptos.join(', ')}</p>
      <p className="mt-1 text-xs text-slate-500">Válido hasta {hora(solicitud.expira_at)}</p>
    </div> : <p role="status" className={`rounded-lg p-3 ${solicitud.estado === 'PAGADA' ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800'}`}>
      {solicitud.estado === 'PAGADA' ? `Pago confirmado. Recibo N.º ${String(solicitud.numero_recibo ?? 0).padStart(6, '0')} por ${formatoMonto(solicitud.monto)}.`
        : `El QR quedó en estado ${solicitud.estado.toLowerCase()}. ${solicitud.observacion}`}
    </p>}
    <Avisos error={error} exito="" />
    <div className="mt-5 flex flex-wrap justify-end gap-2">
      <button className="btn-secondary" onClick={cerrar}>Cerrar</button>
      {solicitud.estado === 'PENDIENTE' && solicitud.simulado && puedeSimular && <button className="btn-secondary" disabled={enviando} onClick={() => void accion(() => simularCobroQR(solicitud.id))}>Simular cobro</button>}
      {solicitud.estado === 'PENDIENTE' && <button className="btn-primary" disabled={enviando} onClick={() => void accion(() => verificarSolicitudQR(solicitud.id))}><RefreshCw size={17} />{enviando ? 'Consultando...' : 'Verificar pago'}</button>}
    </div>
  </Modal>

  return <Modal title="Generar QR de pago" close={cerrar} ancho="max-w-xl">
    <div className="space-y-3">
      <div className="text-sm font-medium">Estudiante<div className="mt-1"><BuscadorEstudiante unidadId={unidadId} seleccionado={estudiante} onSeleccionar={nuevo => void elegir(nuevo)} /></div></div>
      {pendientes.length > 0 && <>
        <p className="text-sm font-medium">Cuotas a cobrar <span className="font-normal text-slate-500">(el QR cobra el saldo completo de cada una)</span></p>
        <ul className="max-h-56 divide-y overflow-y-auto rounded-lg border">
          {pendientes.map(o => <li key={o.id}><label className="flex items-center gap-3 p-2 text-sm">
            <input type="checkbox" aria-label={`Incluir ${o.concepto}`} checked={seleccion.includes(o.id)}
              onChange={() => setSeleccion(seleccion.includes(o.id) ? seleccion.filter(x => x !== o.id) : [...seleccion, o.id])} />
            <span className="flex-1">{o.concepto} <span className="text-xs text-slate-500">· vence {o.fecha_vencimiento}</span>{o.vencida && <span className="ml-2 text-xs font-semibold text-red-600">Vencida</span>}</span>
            <span className="font-semibold">{formatoMonto(o.saldo)}</span>
          </label></li>)}
        </ul>
        <p className="text-right font-semibold">Total del QR: {formatoMonto(totalSeleccion)}</p>
      </>}
    </div>
    <Avisos error={error} exito="" />
    <div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={cerrar}>Cancelar</button>
      <button className="btn-primary" disabled={enviando || !estudiante || seleccion.length === 0} onClick={() => estudiante && void accion(() => crearSolicitudQR({ estudiante: estudiante.id, obligaciones: seleccion }))}><QrCode size={17} />{enviando ? 'Generando...' : 'Generar QR'}</button></div>
  </Modal>
}

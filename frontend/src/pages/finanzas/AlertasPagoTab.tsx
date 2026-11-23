import axios from 'axios'
import { BellRing } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import {
  enviarRecordatoriosPago, formatoMonto, listarRecordatoriosPago,
  type RecordatorioPago, type ResultadoRecordatorios, type TipoRecordatorio,
} from '../../api/finanzas'
import { Avisos, Campo, Tabla } from './comunes'
import { errorTexto, type ContextoFinanzas } from './utilidades'

/** HU-28: recordatorios de cuotas vencidas o por vencer a las familias. */
export default function AlertasPagoTab({ contexto }: { contexto: ContextoFinanzas }) {
  const { unidadId } = contexto
  const { can } = useAuth()
  const [tipo, setTipo] = useState<TipoRecordatorio>('VENCIDAS')
  const [dias, setDias] = useState('5')
  const [resultado, setResultado] = useState<ResultadoRecordatorios | null>(null)
  const [historial, setHistorial] = useState<RecordatorioPago[]>([])
  const [cargando, setCargando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const consulta = useRef<AbortController | null>(null)

  const cargar = useCallback(async () => {
    consulta.current?.abort(); const controller = new AbortController(); consulta.current = controller
    setCargando(true)
    try {
      const { data } = await listarRecordatoriosPago({ unidad_educativa: unidadId }, controller.signal)
      if (!controller.signal.aborted) setHistorial(data)
    } catch (e) { if (!controller.signal.aborted && !axios.isCancel(e)) setError(errorTexto(e, 'No fue posible cargar los recordatorios enviados.')) }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }, [unidadId])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar(); return () => consulta.current?.abort() }, [cargar])

  const enviar = async () => {
    if (!window.confirm('Se enviará un aviso al celular y a la bandeja de cada familia. ¿Continuar?')) return
    setEnviando(true); setError(''); setResultado(null)
    try {
      setResultado((await enviarRecordatoriosPago({ tipo, dias: Number(dias) || 5, unidad_educativa: unidadId })).data)
      void cargar()
    } catch (e) { setError(errorTexto(e, 'No fue posible enviar los recordatorios.')) }
    finally { setEnviando(false) }
  }

  return <div className="space-y-4">
    {can('alerta-pago', 'crear') && <div className="grid gap-3 rounded-2xl bg-white p-4 shadow-sm md:grid-cols-3">
      <Campo label="Avisar sobre"><select aria-label="Tipo de recordatorio" value={tipo} onChange={e => setTipo(e.target.value as TipoRecordatorio)} className="w-full rounded-lg border p-2"><option value="VENCIDAS">Cuotas vencidas</option><option value="POR_VENCER">Cuotas próximas a vencer</option></select></Campo>
      {tipo === 'POR_VENCER' && <Campo label="Que vencen en los próximos (días)"><input aria-label="Días de anticipación" type="number" min="1" max="30" value={dias} onChange={e => setDias(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>}
      <div className="flex items-end"><button className="btn-primary" disabled={enviando} onClick={() => void enviar()}><BellRing size={17} />{enviando ? 'Enviando...' : 'Enviar recordatorios'}</button></div>
    </div>}
    <p className="text-xs text-slate-500">Cada estudiante y sus tutores reciben el monto que deben. Una misma familia no recibe el mismo recordatorio dos veces en el día. Los pagos, anulaciones y becas se notifican solos, y el servidor puede enviar estos recordatorios a diario.</p>
    <Avisos error={error} exito={resultado ? `${resultado.estudiantes_avisados} familia(s) avisadas.${resultado.ya_avisados_hoy ? ` ${resultado.ya_avisados_hoy} ya habían sido avisadas hoy.` : ''}` : ''} />
    <h2 className="text-lg font-semibold">Últimos recordatorios enviados</h2>
    <Tabla columnas={['Fecha', 'Estudiante', 'Tipo', 'Monto avisado']} vacio={historial.length === 0} cargando={cargando}>
      {historial.map(r => <tr key={r.id} className="border-t">
        <td className="p-4">{r.fecha}</td><td className="p-4">{r.estudiante_nombre}</td>
        <td className="p-4">{r.tipo_display}</td><td className="p-4">{formatoMonto(r.monto)}</td>
      </tr>)}
    </Tabla>
  </div>
}

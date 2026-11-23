import { FileDown } from 'lucide-react'
import { useEffect, useState } from 'react'
import { abrirRecibo, formatoMonto, obtenerEstadoCuenta, type EstadoCuenta, type EstudianteElegible } from '../../api/finanzas'
import { Avisos, BuscadorEstudiante, Estado, Tabla, Tarjeta } from './comunes'
import { errorTexto, type ContextoFinanzas } from './utilidades'

export default function EstadoCuentaTab({ contexto }: { contexto: ContextoFinanzas }) {
  const { unidadId, calendarioId } = contexto
  const [estudiante, setEstudiante] = useState<EstudianteElegible | null>(null)
  const [cuenta, setCuenta] = useState<EstadoCuenta | null>(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!estudiante) return
    const controller = new AbortController()
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCargando(true); setError('')
    obtenerEstadoCuenta({ estudiante: estudiante.id, calendario_academico: calendarioId }, controller.signal)
      .then(({ data }) => { if (!controller.signal.aborted) setCuenta(data) })
      .catch(e => { if (!controller.signal.aborted) setError(errorTexto(e, 'No fue posible cargar el estado de cuenta.')) })
      .finally(() => { if (!controller.signal.aborted) setCargando(false) })
    return () => controller.abort()
  }, [estudiante, calendarioId])

  const elegir = (nuevo: EstudianteElegible | null) => { setEstudiante(nuevo); setCuenta(null) }
  const r = cuenta?.resumen
  return <div className="space-y-4">
    <div className="rounded-2xl bg-white p-4 shadow-sm"><div className="max-w-xl text-sm font-medium">Estudiante<div className="mt-1"><BuscadorEstudiante unidadId={unidadId} seleccionado={estudiante} onSeleccionar={elegir} /></div></div></div>
    <Avisos error={error} exito="" />
    {cargando && <p className="text-sm text-slate-500">Cargando estado de cuenta...</p>}
    {cuenta && r && <>
      <div><h2 className="text-lg font-semibold">{cuenta.estudiante_nombre}</h2><p className="text-sm text-slate-500">RUDE {cuenta.rude} · {cuenta.curso_nombre ?? 'Sin curso'}</p></div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tarjeta titulo="Total a pagar" valor={formatoMonto(r.total_a_pagar)} detalle={Number(r.total_descuentos) > 0 ? `Incluye ${formatoMonto(r.total_descuentos)} de beca` : undefined} />
        <Tarjeta titulo="Pagado" valor={formatoMonto(r.total_pagado)} tono="emerald" />
        <Tarjeta titulo="Saldo pendiente" valor={formatoMonto(r.saldo_pendiente)} tono="amber"
          detalle={r.proximo_vencimiento ? `Próximo: ${formatoMonto(r.proximo_monto ?? 0)} el ${r.proximo_vencimiento}` : undefined} />
        <Tarjeta titulo="Vencido" valor={formatoMonto(r.saldo_vencido)} tono={Number(r.saldo_vencido) > 0 ? 'red' : 'slate'} />
      </div>
      <h3 className="font-semibold">Cuotas</h3>
      <Tabla columnas={['Concepto', 'Vence', 'Monto', 'Descuento', 'Pagado', 'Saldo', 'Estado']} cargando={false} vacio={cuenta.obligaciones.length === 0}>
        {cuenta.obligaciones.map(o => <tr key={o.id} className="border-t">
          <td className="p-4">{o.concepto}<p className="text-xs text-slate-500">{o.plan_nombre}</p></td>
          <td className="p-4">{o.fecha_vencimiento}</td>
          <td className="p-4">{formatoMonto(o.monto_original)}</td>
          <td className="p-4">{Number(o.descuento) > 0 ? formatoMonto(o.descuento) : '—'}</td>
          <td className="p-4">{formatoMonto(o.monto_pagado)}</td>
          <td className="p-4 font-semibold">{formatoMonto(o.saldo)}</td>
          <td className="p-4"><Estado valor={o.vencida ? 'VENCIDA' : o.estado} /></td>
        </tr>)}
      </Tabla>
      <h3 className="font-semibold">Pagos</h3>
      <Tabla columnas={['Recibo', 'Fecha', 'Método', 'Monto', 'Estado', '']} cargando={false} vacio={cuenta.pagos.length === 0}>
        {cuenta.pagos.map(p => <tr key={p.id} className="border-t">
          <td className="p-4 font-mono">{String(p.numero_recibo).padStart(6, '0')}</td>
          <td className="p-4">{p.fecha_pago}</td>
          <td className="p-4">{p.metodo_display}</td>
          <td className="p-4">{formatoMonto(p.monto)}</td>
          <td className="p-4"><Estado valor={p.estado} /></td>
          <td className="p-4"><button aria-label={`Descargar recibo ${p.numero_recibo}`} title="Descargar recibo" onClick={() => void abrirRecibo(p).catch(e => setError(errorTexto(e, 'No fue posible descargar el recibo.')))}><FileDown size={18} /></button></td>
        </tr>)}
      </Tabla>
    </>}
  </div>
}

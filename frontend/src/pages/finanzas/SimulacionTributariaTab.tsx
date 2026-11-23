import { Calculator } from 'lucide-react'
import { useState } from 'react'
import { formatoMonto, simularTributos, type Impuestos, type SimulacionTributaria } from '../../api/finanzas'
import { Avisos, Campo } from './comunes'
import { errorTexto, type ContextoFinanzas } from './utilidades'

const fecha = (d: Date) => d.toLocaleDateString('en-CA')
const inicioDeMes = () => { const d = new Date(); return fecha(new Date(d.getFullYear(), d.getMonth(), 1)) }
const finDeMes = () => { const d = new Date(); return fecha(new Date(d.getFullYear(), d.getMonth() + 1, 0)) }

const FILAS: [keyof Impuestos, string, boolean?][] = [
  ['base_imponible', 'Ingresos (base imponible)'],
  ['debito_fiscal_iva', 'Débito fiscal IVA'],
  ['credito_fiscal', '(−) Crédito fiscal'],
  ['iva_a_pagar', 'IVA a pagar', true],
  ['it', 'IT a pagar', true],
  ['total_impuestos', 'Total impuestos', true],
  ['ingreso_neto', 'Ingreso neto estimado', true],
]

function Columna({ titulo, impuestos, nota }: { titulo: string; impuestos: Impuestos; nota?: string }) {
  return <div className="rounded-2xl bg-white p-4 shadow-sm">
    <h3 className="font-semibold">{titulo}</h3>
    {nota && <p className="text-xs text-slate-500">{nota}</p>}
    <dl className="mt-3 divide-y text-sm">
      {FILAS.map(([clave, etiqueta, destacada]) => <div key={clave} className={`flex justify-between py-2 ${destacada ? 'font-semibold' : ''}`}>
        <dt>{etiqueta}</dt><dd>{formatoMonto(impuestos[clave])}</dd>
      </div>)}
      {Number(impuestos.saldo_a_favor) > 0 && <div className="flex justify-between py-2 text-emerald-700"><dt>Saldo a favor (crédito)</dt><dd>{formatoMonto(impuestos.saldo_a_favor)}</dd></div>}
    </dl>
  </div>
}

export default function SimulacionTributariaTab({ contexto }: { contexto: ContextoFinanzas }) {
  const { unidadId } = contexto
  const [desde, setDesde] = useState(inicioDeMes())
  const [hasta, setHasta] = useState(finDeMes())
  const [credito, setCredito] = useState('0')
  const [tasaIva, setTasaIva] = useState('13')
  const [tasaIt, setTasaIt] = useState('3')
  const [resultado, setResultado] = useState<SimulacionTributaria | null>(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')

  const simular = async () => {
    if (!desde || !hasta || hasta < desde) { setError('Indique un rango de fechas válido.'); return }
    setCargando(true); setError('')
    try {
      const { data } = await simularTributos({ unidad_educativa: unidadId, desde, hasta, credito_fiscal: credito || 0, tasa_iva: tasaIva, tasa_it: tasaIt })
      setResultado(data)
    } catch (e) { setError(errorTexto(e, 'No fue posible realizar la simulación.')) }
    finally { setCargando(false) }
  }

  return <div className="space-y-4">
    <div className="grid gap-3 rounded-2xl bg-white p-4 shadow-sm md:grid-cols-6">
      <Campo label="Desde"><input aria-label="Desde" type="date" value={desde} onChange={e => setDesde(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>
      <Campo label="Hasta"><input aria-label="Hasta" type="date" value={hasta} onChange={e => setHasta(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>
      <Campo label="Crédito fiscal (Bs)"><input aria-label="Crédito fiscal" type="number" min="0" step="0.01" value={credito} onChange={e => setCredito(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>
      <Campo label="Tasa IVA (%)"><input aria-label="Tasa IVA" type="number" min="0" max="100" step="0.01" value={tasaIva} onChange={e => setTasaIva(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>
      <Campo label="Tasa IT (%)"><input aria-label="Tasa IT" type="number" min="0" max="100" step="0.01" value={tasaIt} onChange={e => setTasaIt(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>
      <div className="flex items-end"><button className="btn-primary w-full" disabled={cargando} onClick={() => void simular()}><Calculator size={17} />{cargando ? 'Calculando...' : 'Simular'}</button></div>
    </div>
    <p className="text-xs text-slate-500">Simulación referencial: el IVA se considera incluido en el precio (débito = tasa × total cobrado) y el IT se aplica sobre el ingreso bruto. No reemplaza la declaración ante Impuestos Nacionales.</p>
    <Avisos error={error} exito="" />
    {resultado && <>
      <div className="grid gap-4 md:grid-cols-2">
        <Columna titulo="Sobre lo cobrado" nota={`Pagos válidos del ${resultado.desde} al ${resultado.hasta}`} impuestos={resultado.cobrado} />
        <Columna titulo="Proyección (cobrado + pendiente)" nota={`Incluye ${formatoMonto(resultado.proyectado.pendiente_por_cobrar)} por cobrar que vence en el rango`} impuestos={resultado.proyectado} />
      </div>
      {resultado.mensual.length > 0 && <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
        <table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr><th className="p-4">Mes</th><th className="p-4">Pagos</th><th className="p-4">Cobrado</th><th className="p-4">IVA (débito)</th><th className="p-4">IT</th></tr></thead>
          <tbody>{resultado.mensual.map(m => <tr key={m.mes} className="border-t">
            <td className="p-4">{m.mes}</td><td className="p-4">{m.pagos}</td><td className="p-4">{formatoMonto(m.cobrado)}</td>
            <td className="p-4">{formatoMonto(Number(m.cobrado) * Number(resultado.tasa_iva) / 100)}</td>
            <td className="p-4">{formatoMonto(Number(m.cobrado) * Number(resultado.tasa_it) / 100)}</td>
          </tr>)}</tbody></table>
      </div>}
    </>}
  </div>
}

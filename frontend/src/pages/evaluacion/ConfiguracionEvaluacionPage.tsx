import axios from 'axios'
import { Save, Scale } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import {
  configurarDimensionesEvaluacion, listarCalendarios, listarConfiguracionesEvaluacion,
  type Calendario, type ConfiguracionEvaluacion, type DimensionPayload, type NivelEvaluacion,
  type ReglaRedondeo,
} from '../../api/configuracionEvaluacion'

const NIVELES: Array<[NivelEvaluacion, string]> = [['PRI', 'Primaria'], ['SEC', 'Secundaria'], ['INI', 'Inicial']]
const REGLAS: Array<[ReglaRedondeo, string]> = [['NORMAL', 'Normal (≥0.5 sube)'], ['TRUNCAR', 'Truncar'], ['SUPERIOR', 'Siempre al superior']]

const dimensionesOficiales: DimensionPayload[] = [
  { codigo: 'SER', nombre: 'Ser', ponderacion: '10', orden: 1 },
  { codigo: 'SABER', nombre: 'Saber', ponderacion: '35', orden: 2 },
  { codigo: 'HACER', nombre: 'Hacer', ponderacion: '35', orden: 3 },
  { codigo: 'DECIDIR', nombre: 'Decidir', ponderacion: '10', orden: 4 },
  { codigo: 'AUTOEVAL', nombre: 'Autoevaluación', ponderacion: '10', orden: 5 },
]

const generalInicial = { nota_minima: '0', nota_maxima: '100', nota_aprobacion: '51', decimales: '0', regla_redondeo: 'NORMAL' as ReglaRedondeo }

export default function ConfiguracionEvaluacionPage() {
  const [calendarios, setCalendarios] = useState<Calendario[]>([])
  const [calendarioId, setCalendarioId] = useState('')
  const [nivel, setNivel] = useState<NivelEvaluacion>('PRI')
  const [general, setGeneral] = useState(generalInicial)
  const [dimensiones, setDimensiones] = useState<DimensionPayload[]>(dimensionesOficiales)
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')

  useEffect(() => {
    listarCalendarios().then(setCalendarios).catch(() => setError('No fue posible cargar las gestiones académicas.')).finally(() => setCargando(false))
  }, [])

  const cargarConfiguracion = useCallback(async () => {
    if (!calendarioId) return
    setError(''); setExito('')
    try {
      const { data } = await listarConfiguracionesEvaluacion({ calendario_academico: Number(calendarioId), nivel })
      const lista: ConfiguracionEvaluacion[] = Array.isArray(data) ? data : data.results
      const existente = lista[0]
      if (existente) {
        setGeneral({
          nota_minima: existente.nota_minima, nota_maxima: existente.nota_maxima,
          nota_aprobacion: existente.nota_aprobacion, decimales: String(existente.decimales),
          regla_redondeo: existente.regla_redondeo,
        })
        setDimensiones(existente.dimensiones
          .slice().sort((a, b) => a.orden - b.orden)
          .map((d) => ({ codigo: d.codigo, nombre: d.nombre, ponderacion: d.ponderacion, orden: d.orden })))
      } else {
        setGeneral(generalInicial)
        setDimensiones(dimensionesOficiales)
      }
    } catch (e) {
      setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para consultar esta configuración.' : 'No fue posible cargar la configuración.')
    }
  }, [calendarioId, nivel])
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargarConfiguracion() }, [cargarConfiguracion])

  const suma = dimensiones.reduce((acc, d) => acc + (Number(d.ponderacion) || 0), 0)
  const sumaValida = suma === 100

  const actualizarDimension = (indice: number, campo: 'nombre' | 'ponderacion', valor: string) =>
    setDimensiones((previas) => previas.map((d, i) => (i === indice ? { ...d, [campo]: valor } : d)))

  const guardar = async () => {
    if (!calendarioId || !sumaValida || guardando) return
    setGuardando(true); setError(''); setExito('')
    try {
      await configurarDimensionesEvaluacion({
        calendario_academico: Number(calendarioId), nivel,
        nota_minima: general.nota_minima, nota_maxima: general.nota_maxima,
        nota_aprobacion: general.nota_aprobacion, decimales: Number(general.decimales),
        regla_redondeo: general.regla_redondeo, dimensiones,
      })
      setExito('Configuración de evaluación guardada correctamente.')
    } catch (e) {
      const respuesta = axios.isAxiosError(e) ? e.response : undefined
      setError(respuesta?.status === 403 ? 'No tiene permiso para configurar esta gestión académica.' : mensajeDominio(respuesta?.data))
    } finally { setGuardando(false) }
  }

  return <section className="p-4 sm:p-6 lg:p-8" aria-labelledby="config-evaluacion-titulo">
    <header className="mb-6">
      <div className="flex items-center gap-3"><Scale className="text-teal-700" /><h1 id="config-evaluacion-titulo" className="text-2xl font-bold">Configuración de evaluación</h1></div>
      <p className="mt-1 text-sm text-slate-500">Dimensiones Ser, Saber, Hacer, Decidir y Autoevaluación por gestión académica y nivel (Ley N.º 070).</p>
    </header>

    <div className="mb-5 grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-2">
      <Select label="Gestión académica" value={calendarioId} onChange={setCalendarioId}
        opciones={[['', 'Seleccione'], ...calendarios.map((c) => [String(c.id), `${c.unidad_nombre} - ${c.año}`])]} />
      <Select label="Nivel educativo" value={nivel} onChange={(v) => setNivel(v as NivelEvaluacion)}
        opciones={NIVELES.map(([valor, etiqueta]) => [valor, etiqueta])} />
    </div>

    {cargando && <p className="p-8 text-center text-slate-500">Cargando gestiones académicas...</p>}
    {exito && <p role="status" className="mb-4 rounded-xl bg-emerald-50 p-3 text-emerald-700">{exito}</p>}
    {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}

    {!cargando && calendarioId && <>
      <div className="mb-5 grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-3 lg:grid-cols-5">
        <Campo label="Nota mínima" type="number" value={general.nota_minima} onChange={(v) => setGeneral({ ...general, nota_minima: v })} />
        <Campo label="Nota máxima" type="number" value={general.nota_maxima} onChange={(v) => setGeneral({ ...general, nota_maxima: v })} />
        <Campo label="Nota de aprobación" type="number" value={general.nota_aprobacion} onChange={(v) => setGeneral({ ...general, nota_aprobacion: v })} />
        <Campo label="Decimales" type="number" value={general.decimales} onChange={(v) => setGeneral({ ...general, decimales: v })} />
        <Select label="Regla de redondeo" value={general.regla_redondeo} onChange={(v) => setGeneral({ ...general, regla_redondeo: v as ReglaRedondeo })}
          opciones={REGLAS.map(([valor, etiqueta]) => [valor, etiqueta])} />
      </div>

      <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50"><tr>{['Código', 'Dimensión', 'Ponderación (pts)'].map((x) => <th key={x} className="px-4 py-3">{x}</th>)}</tr></thead>
          <tbody>
            {dimensiones.map((d, indice) => <tr key={d.codigo} className="border-t border-slate-100">
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{d.codigo}</td>
              <td className="px-4 py-3">
                <input aria-label={`Nombre de ${d.codigo}`} value={d.nombre} onChange={(e) => actualizarDimension(indice, 'nombre', e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2" />
              </td>
              <td className="px-4 py-3">
                <input aria-label={`Ponderación de ${d.codigo}`} type="number" min={0} max={100} step="0.01" value={d.ponderacion}
                  onChange={(e) => actualizarDimension(indice, 'ponderacion', e.target.value)}
                  className="w-28 rounded-lg border border-slate-300 px-3 py-2" />
              </td>
            </tr>)}
          </tbody>
          <tfoot>
            <tr className="border-t border-slate-200">
              <td className="px-4 py-3" colSpan={2}>Suma de ponderaciones</td>
              <td className={`px-4 py-3 font-semibold ${sumaValida ? 'text-emerald-700' : 'text-red-600'}`}>{suma} / 100</td>
            </tr>
          </tfoot>
        </table>
      </div>
      {!sumaValida && <p className="mt-2 text-sm text-red-600">La suma de las ponderaciones debe ser exactamente 100 para poder guardar.</p>}

      <div className="mt-5 flex justify-end">
        <button className="btn-primary" disabled={!sumaValida || guardando} onClick={() => void guardar()}>
          <Save size={18} />{guardando ? 'Guardando...' : 'Guardar configuración'}
        </button>
      </div>
    </>}
  </section>
}

function Campo({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return <label className="text-sm font-medium">{label}<input aria-label={label} type={type} value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
}
function Select({ label, value, onChange, opciones }: { label: string; value: string; onChange: (v: string) => void; opciones: string[][] }) {
  return <label className="text-sm font-medium">{label}<select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2">{opciones.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
}
function mensajeDominio(data: unknown) {
  if (!data || typeof data !== 'object') return 'Revise los datos ingresados.'
  return Object.entries(data as Record<string, unknown>).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : String(v)}`).join(' ')
}

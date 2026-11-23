import axios from 'axios'
import { Download, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import FilterValueInput, { convertirValor } from './components/FilterValueInput'
import { normalizarErrores } from './components/erroresReportes'
import {
  actualizarDefinicionReporteOperativo, catalogoReportesOperativos, crearDefinicionReporteOperativo,
  definicionesReportesOperativos, exportarReporteOperativo, previsualizarReporteOperativo,
  type DefinicionReporteOperativo, type EspecificacionReporteOperativo, type FuenteReporteOperativo, type VistaPreviaReporte,
} from '../../api/reportes'

export default function ReportesOperativosPanel({ onExportado }: { onExportado?: () => void } = {}) {
  const [fuentes, setFuentes] = useState<FuenteReporteOperativo[]>([])
  const [definiciones, setDefiniciones] = useState<DefinicionReporteOperativo[]>([])
  const [codigo, setCodigo] = useState('')
  const [filtro, setFiltro] = useState('')
  const [valor, setValor] = useState('')
  const [vista, setVista] = useState<VistaPreviaReporte | null>(null)
  const [error, setError] = useState('')
  const [errorValor, setErrorValor] = useState('')
  const [errorFiltro, setErrorFiltro] = useState('')
  const [cargando, setCargando] = useState(false)
  const fuente = useMemo(() => fuentes.find((item) => item.codigo === codigo), [fuentes, codigo])

  useEffect(() => {
    Promise.all([catalogoReportesOperativos(), definicionesReportesOperativos()])
      .then(([catalogo, definiciones]) => {
        setFuentes(catalogo.data.results)
        setDefiniciones(definiciones.data.results)
        setCodigo(catalogo.data.results[0]?.codigo ?? '')
      })
      .catch((e) => setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para este reporte.' : 'No fue posible cargar los reportes operativos.'))
  }, [])

  const especificacion = (): EspecificacionReporteOperativo => ({
    columnas: fuente?.predeterminadas ?? [],
    filtros: filtro && fuente
      ? [{ campo: filtro, operador: fuente.filtros.find((item) => item.campo === filtro)?.operadores.includes('eq') ? 'eq' : 'contains', valor: convertirValor(fuente.filtros.find((item) => item.campo === filtro)!, fuente.filtros.find((item) => item.campo === filtro)?.operadores.includes('eq') ? 'eq' : 'contains', valor) }]
      : [],
    orden: [],
  })

  const preparar = async () => {
    if (!fuente) throw new Error('Fuente no disponible')
    const spec = especificacion()
    const existente = definiciones.find((item) => item.codigo_fuente === fuente.codigo)
    if (existente) {
      await actualizarDefinicionReporteOperativo(existente.id, spec)
      return existente.id
    }
    const { data } = await crearDefinicionReporteOperativo({
      nombre: `Operativo ${fuente.nombre}`, codigo_fuente: fuente.codigo, especificacion: spec,
    })
    setDefiniciones((actuales) => [...actuales, data])
    return data.id
  }

  const manejarError = (e: unknown, alternativo: string) => {
    if (!axios.isAxiosError(e)) { setErrorValor(e instanceof Error ? e.message : alternativo); return }
    if (e.response?.status === 403) { setError('No tiene permiso para este reporte.'); return }
    const errores = normalizarErrores(e.response?.data)
    for (const item of errores) {
      if (item.ruta.includes('valor')) setErrorValor(item.mensaje)
      else if (item.ruta.includes('campo') || item.ruta.includes('operador')) setErrorFiltro(item.mensaje)
      else setError(item.mensaje)
    }
    if (!errores.length) setError(alternativo)
  }

  const consultar = async () => {
    setCargando(true); setError(''); setErrorValor('')
    try { setVista((await previsualizarReporteOperativo(await preparar())).data) }
    catch (e) { manejarError(e, 'No fue posible generar la vista previa.') }
    finally { setCargando(false) }
  }

  const exportar = async (formato: 'CSV' | 'PDF') => {
    setCargando(true); setError(''); setErrorValor('')
    try {
      const { data } = await exportarReporteOperativo(await preparar(), formato)
      const url = URL.createObjectURL(data as Blob); const enlace = document.createElement('a')
      enlace.href = url; enlace.download = `reporte-operativo.${formato.toLowerCase()}`; enlace.click(); URL.revokeObjectURL(url)
      onExportado?.()
    } catch (e) { manejarError(e, 'No fue posible exportar el reporte.') }
    finally { setCargando(false) }
  }

  return <section className="mb-8 rounded-2xl bg-white p-4 shadow-sm" aria-labelledby="operativos-titulo">
    <h2 id="operativos-titulo" className="text-lg font-semibold">Reportes operativos</h2>
    <p className="mb-3 text-sm text-slate-500">La vista previa muestra hasta 100 filas; las exportaciones, hasta 5.000.</p>
    {error && <p role="alert" className="mb-3 text-sm text-red-700">{error}</p>}
    <div className="grid gap-3 md:grid-cols-3">
      <label className="text-sm">Reporte<select className="mt-1 w-full rounded border p-2" value={codigo} onChange={(e) => { setCodigo(e.target.value); setFiltro(''); setValor(''); setVista(null); setError(''); setErrorValor(''); setErrorFiltro('') }}>
        {fuentes.map((item) => <option key={item.codigo} value={item.codigo}>{item.nombre}</option>)}
      </select></label>
      <label className="text-sm">Filtro opcional<select className="mt-1 w-full rounded border p-2" value={filtro} onChange={(e) => { setFiltro(e.target.value); setValor(''); setErrorValor(''); setErrorFiltro('') }}>
        <option value="">Sin filtro</option>{fuente?.filtros.map((item) => <option key={item.campo} value={item.campo}>{item.campo}</option>)}
      </select>{errorFiltro && <span role="alert" className="text-red-700">{errorFiltro}</span>}</label>
      <div className="text-sm">Valor<FilterValueInput key={`${codigo}-${filtro}`} filtro={fuente?.filtros.find((item) => item.campo === filtro)} operador="eq" valor={valor} onChange={(nuevo) => { setValor(nuevo); setErrorValor('') }} error={errorValor} /></div>
    </div>
    <div className="mt-3 flex flex-wrap gap-2"><button type="button" className="rounded bg-slate-800 px-3 py-2 text-sm text-white disabled:opacity-50" disabled={!fuente || cargando} onClick={consultar}><Search className="mr-1 inline h-4 w-4" />Vista previa</button>
      <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={!fuente || cargando} onClick={() => exportar('CSV')}><Download className="mr-1 inline h-4 w-4" />CSV</button>
      <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={!fuente || cargando} onClick={() => exportar('PDF')}><Download className="mr-1 inline h-4 w-4" />PDF</button></div>
    {vista && <div className="mt-4 overflow-auto rounded border border-slate-200 p-3" aria-live="polite"><div className="mb-2 flex items-center justify-between gap-3"><p className="text-sm">{vista.cantidad} fila(s){vista.limite_alcanzado ? ' (límite alcanzado)' : ''}</p><button type="button" className="rounded border px-3 py-1 text-sm" onClick={() => setVista(null)}>Limpiar vista previa</button></div><table className="min-w-full text-sm"><thead><tr>{vista.columnas.map((columna) => <th key={columna.campo} className="border p-2 text-left">{columna.etiqueta}</th>)}</tr></thead><tbody>{vista.filas.map((fila, indice) => <tr key={indice}>{fila.map((celda, celdaIndice) => <td key={celdaIndice} className="border p-2">{String(celda ?? '')}</td>)}</tr>)}</tbody></table></div>}
  </section>
}

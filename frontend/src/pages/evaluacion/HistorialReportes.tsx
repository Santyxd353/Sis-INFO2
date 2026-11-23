import axios from 'axios'
import { useEffect, useState } from 'react'
import { archivarEjecucion, descargarEjecucion, detalleEjecucion, listarEjecuciones, type EjecucionReporte } from '../../api/reportes'

export default function HistorialReportes({ version, puedeArchivar }: { version: number; puedeArchivar: boolean }) {
  const [items, setItems] = useState<EjecucionReporte[]>([])
  const [filtros, setFiltros] = useState<Record<string, string>>({})
  const [pagina, setPagina] = useState(1)
  const [total, setTotal] = useState(0)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [recarga, setRecarga] = useState(0)
  const [detalle, setDetalle] = useState<EjecucionReporte | null>(null)
  useEffect(() => {
    let vigente = true
    listarEjecuciones({ ...filtros, page: pagina }).then(({ data }) => {
      if (vigente) { setItems(data.results); setTotal(data.count); setError('') }
    }).catch((e: unknown) => {
      if (vigente) setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para consultar el historial.' : 'No fue posible cargar el historial.')
    }).finally(() => { if (vigente) setCargando(false) })
    return () => { vigente = false }
  }, [filtros, pagina, recarga, version])
  const cambiar = (campo: string, valor: string) => { setCargando(true); setPagina(1); setFiltros((actual) => ({ ...actual, [campo]: valor })) }
  const accion = async (fn: () => Promise<unknown>) => {
    try { await fn() } catch (e) { setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para esta acción.' : 'No fue posible completar la acción.') }
  }
  return <section className="mb-8 rounded-2xl bg-white p-4 shadow-sm" aria-labelledby="historial-titulo">
    <h2 id="historial-titulo" className="text-lg font-semibold">Historial de reportes</h2>
    <div className="my-3 flex flex-wrap gap-3">
      <label>Fuente <input className="rounded border p-1" value={filtros.fuente ?? ''} onChange={(e) => cambiar('fuente', e.target.value)} /></label>
      <label>Formato <select value={filtros.formato ?? ''} onChange={(e) => cambiar('formato', e.target.value)}><option value="">Todos</option><option>CSV</option><option>PDF</option></select></label>
      <label>Estado <select value={filtros.estado ?? ''} onChange={(e) => cambiar('estado', e.target.value)}><option value="">Todos</option>{['PENDIENTE', 'EN_PROCESO', 'COMPLETADO', 'ERROR', 'CANCELADO'].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>Unidad <input type="number" min="1" className="w-20 rounded border p-1" value={filtros.unidad ?? ''} onChange={(e) => cambiar('unidad', e.target.value)} /></label>
      <label>Desde <input type="date" value={filtros.desde ?? ''} onChange={(e) => cambiar('desde', e.target.value)} /></label>
      <label>Hasta <input type="date" value={filtros.hasta ?? ''} onChange={(e) => cambiar('hasta', e.target.value)} /></label>
      {puedeArchivar && <label><input type="checkbox" checked={filtros.archivados === 'true'} onChange={(e) => cambiar('archivados', String(e.target.checked))} /> Archivados</label>}
    </div>
    {cargando && <p role="status">Cargando historial…</p>}
    {error && <p role="alert">{error} <button type="button" onClick={() => { setCargando(true); setRecarga((v) => v + 1) }}>Reintentar</button></p>}
    {!cargando && !error && (items.length ? <div className="overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{['Reporte', 'Tipo', 'Formato', 'Unidad', 'Ejecutor', 'Estado', 'Fecha', 'Tamaño', 'Acciones'].map((x) => <th key={x} className="p-2">{x}</th>)}</tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-t"><td>{item.nombre}</td><td>{item.tipo}</td><td>{item.formato}</td><td>{item.unidad ?? 'Colegio'}</td><td>{item.ejecutor ?? '—'}</td><td>{item.archivado_at ? 'ARCHIVADO' : item.estado}</td><td>{new Date(item.iniciada_at).toLocaleString()}</td><td>{item.tamano == null ? '—' : `${item.tamano} bytes`}</td><td className="space-x-2"><button type="button" onClick={() => void accion(async () => setDetalle((await detalleEjecucion(item.id)).data))}>Detalle</button>{item.estado === 'COMPLETADO' && !item.archivado_at && <button type="button" onClick={() => void accion(() => descargarEjecucion(item))}>Descargar</button>}{puedeArchivar && !item.archivado_at && <button type="button" onClick={() => void accion(async () => { await archivarEjecucion(item.id); setRecarga((v) => v + 1) })}>Archivar</button>}</td></tr>)}</tbody></table></div> : <p>No hay reportes para estos filtros.</p>)}
    <div className="mt-3 flex gap-3"><button type="button" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>Anterior</button><span>Página {pagina}</span><button type="button" disabled={pagina * 20 >= total} onClick={() => setPagina((p) => p + 1)}>Siguiente</button></div>
    {detalle && <div className="mt-3 rounded border p-3"><h3>Detalle del reporte</h3><p>{detalle.nombre} · {detalle.fuente_nombre ?? detalle.fuente} · {detalle.estado}</p><button type="button" onClick={() => setDetalle(null)}>Cerrar detalle</button></div>}
  </section>
}

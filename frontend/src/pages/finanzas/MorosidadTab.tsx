import axios from 'axios'
import { useCallback, useEffect, useRef, useState } from 'react'
import { cargarCatalogoPaginado } from '../../api/catalogosPaginados'
import { formatoMonto, obtenerMorosidad, type Morosidad } from '../../api/finanzas'
import { Avisos, Campo, Tabla, Tarjeta } from './comunes'
import { errorTexto, type ContextoFinanzas } from './utilidades'

const COLOR_TRAMO: Record<string, string> = {
  '1-30': 'bg-amber-50 text-amber-700', '31-60': 'bg-orange-50 text-orange-700',
  '61-90': 'bg-red-50 text-red-700', '90+': 'bg-red-100 text-red-800',
}

export default function MorosidadTab({ contexto }: { contexto: ContextoFinanzas }) {
  const { unidadId, calendarioId } = contexto
  const [datos, setDatos] = useState<Morosidad | null>(null)
  const [curso, setCurso] = useState('')
  const [dias, setDias] = useState('1')
  const [cursos, setCursos] = useState<{ id: number; nombre: string }[]>([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const consulta = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    cargarCatalogoPaginado<{ id: number; nombre: string }>('/academico/cursos/', { unidad_educativa: unidadId }, controller.signal)
      .then(data => { if (!controller.signal.aborted) setCursos(data) })
      .catch(e => { if (!controller.signal.aborted) setError(errorTexto(e, 'No fue posible cargar los cursos.')) })
    return () => controller.abort()
  }, [unidadId])

  const cargar = useCallback(async () => {
    consulta.current?.abort(); const controller = new AbortController(); consulta.current = controller
    setCargando(true); setError('')
    try {
      const { data } = await obtenerMorosidad({ unidad_educativa: unidadId, calendario_academico: calendarioId, curso: curso || undefined, dias_minimos: Number(dias) || 1 }, controller.signal)
      if (!controller.signal.aborted) setDatos(data)
    } catch (e) { if (!controller.signal.aborted && !axios.isCancel(e)) setError(errorTexto(e, 'No fue posible cargar la morosidad.')) }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }, [unidadId, calendarioId, curso, dias])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar(); return () => consulta.current?.abort() }, [cargar])

  const r = datos?.resumen
  return <div className="space-y-4">
    <div className="grid gap-3 rounded-2xl bg-white p-4 shadow-sm md:grid-cols-3">
      <Campo label="Curso"><select aria-label="Curso" value={curso} onChange={e => setCurso(e.target.value)} className="w-full rounded-lg border p-2"><option value="">Todos</option>{cursos.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></Campo>
      <Campo label="Días mínimos de mora"><select aria-label="Días mínimos de mora" value={dias} onChange={e => setDias(e.target.value)} className="w-full rounded-lg border p-2"><option value="1">Cualquier atraso</option><option value="31">Más de 30 días</option><option value="61">Más de 60 días</option><option value="91">Más de 90 días</option></select></Campo>
      {datos && <p className="self-end pb-2 text-right text-sm text-slate-500">Fecha de corte: {datos.fecha_corte}</p>}
    </div>
    <Avisos error={error} exito="" reintentar={() => void cargar()} />
    {r && <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tarjeta titulo="Estudiantes en mora" valor={`${r.estudiantes_morosos} / ${r.estudiantes_con_cuotas}`} tono={r.estudiantes_morosos ? 'red' : 'emerald'} detalle="con cuotas asignadas" />
        <Tarjeta titulo="Monto vencido" valor={formatoMonto(r.monto_vencido)} tono="red" />
        <Tarjeta titulo="Monto exigible a la fecha" valor={formatoMonto(r.monto_exigible)} />
        <Tarjeta titulo="Índice de morosidad" valor={`${Number(r.indice_morosidad).toFixed(2)}%`} tono={Number(r.indice_morosidad) > 15 ? 'red' : 'amber'} detalle="vencido / exigible" />
      </div>
      <div className="flex flex-wrap gap-2" aria-label="Antigüedad de la deuda">
        {r.por_tramo.map(t => <span key={t.tramo} className={`rounded-full px-3 py-1 text-sm font-medium ${COLOR_TRAMO[t.tramo]}`}>{t.tramo} días: {t.estudiantes} est. · {formatoMonto(t.monto)}</span>)}
      </div>
    </>}
    <Tabla columnas={['Estudiante', 'Curso', 'Cuotas vencidas', 'Monto vencido', 'Vence desde', 'Días de mora', 'Tramo']} cargando={cargando} vacio={!datos || datos.estudiantes.length === 0}>
      {datos?.estudiantes.map(f => <tr key={f.estudiante} className="border-t">
        <td className="p-4 font-medium">{f.estudiante_nombre}</td>
        <td className="p-4">{f.curso_nombre ?? '—'}</td>
        <td className="p-4">{f.cuotas_vencidas}</td>
        <td className="p-4 font-semibold text-red-700">{formatoMonto(f.monto_vencido)}</td>
        <td className="p-4">{f.vencimiento_mas_antiguo}</td>
        <td className="p-4">{f.dias_mora}</td>
        <td className="p-4"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${COLOR_TRAMO[f.tramo]}`}>{f.tramo}</span></td>
      </tr>)}
    </Tabla>
  </div>
}

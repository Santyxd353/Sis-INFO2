import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import axiosInstance from '../../api/axiosInstance'
import { listarUnidadesCatalogo } from '../../api/catalogosInstitucionales'
import { listarCalendarios, listarCursos, listarMateriasCurso, type Calendario, type Curso, type MateriaCurso } from '../../api/asignacionesDocentes'
import { exportarAnalitica, resumenAnalitica, type FiltrosAnalitica, type ResumenAnalitica } from '../../api/reportes'
import type { UnidadEducativa } from '../../app/modelos/Institucion'
import { useAuth } from '../../app/contexts/AuthContext'
import VozPanel from './VozPanel'

type Opcion = { id: number; nombre: string }

export default function AnaliticaPanel({ onExportado, modo = 'analitica' }: { onExportado: () => void; modo?: 'analitica' | 'voz' }) {
  const { user } = useAuth()
  const alcance = user?.alcance
  const [unidades, setUnidades] = useState<UnidadEducativa[]>([])
  const [calendarios, setCalendarios] = useState<Calendario[]>([])
  const [cursos, setCursos] = useState<Curso[]>([])
  const [periodos, setPeriodos] = useState<Opcion[]>([])
  const [materias, setMaterias] = useState<MateriaCurso[]>([])
  const [unidad, setUnidad] = useState(alcance?.unidad_id ? String(alcance.unidad_id) : '')
  const [calendario, setCalendario] = useState('')
  const [periodo, setPeriodo] = useState('')
  const [curso, setCurso] = useState('')
  const [materia, setMateria] = useState('')
  const [datos, setDatos] = useState<ResumenAnalitica | null>(null)
  const [aplicados, setAplicados] = useState<FiltrosAnalitica | null>(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)
  const consulta = useRef<AbortController | null>(null)
  const exportacion = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    listarUnidadesCatalogo(alcance?.colegio_id ?? undefined, controller.signal).then(v => { if (!controller.signal.aborted) setUnidades(v) }).catch(() => { if (!controller.signal.aborted) setError('No se pudieron cargar las unidades.') })
    return () => controller.abort()
  }, [alcance?.colegio_id])
  useEffect(() => {
    const controller = new AbortController()
    if (unidad) Promise.all([listarCalendarios(Number(unidad), controller.signal), listarCursos(Number(unidad), controller.signal)]).then(([cs, cursosNuevos]) => { if (!controller.signal.aborted) { setCalendarios(cs); setCursos(cursosNuevos) } }).catch(() => { if (!controller.signal.aborted) setError('No se pudieron cargar los filtros institucionales.') })
    return () => controller.abort()
  }, [unidad])
  useEffect(() => {
    const controller = new AbortController()
    if (calendario) axiosInstance.get('/calendario/periodos/', { params: { calendario }, signal: controller.signal }).then(({ data }) => { if (!controller.signal.aborted) setPeriodos(Array.isArray(data) ? data : data.results) }).catch(() => { if (!controller.signal.aborted) setError('No se pudieron cargar los periodos.') })
    return () => controller.abort()
  }, [calendario])
  useEffect(() => {
    const controller = new AbortController()
    if (curso) listarMateriasCurso(Number(curso), controller.signal).then(v => { if (!controller.signal.aborted) setMaterias(v) }).catch(() => { if (!controller.signal.aborted) setError('No se pudieron cargar las materias.') })
    return () => controller.abort()
  }, [curso])
  useEffect(() => () => { consulta.current?.abort(); exportacion.current?.abort() }, [])

  const limpiarResultado = () => { consulta.current?.abort(); exportacion.current?.abort(); setDatos(null); setAplicados(null); setCargando(false) }
  const aplicar = async () => {
    if (!unidad || !calendario) { setError('Seleccione unidad y gestión académica.'); return }
    const filtros: FiltrosAnalitica = { unidad_educativa: Number(unidad), calendario_academico: Number(calendario), ...(periodo ? { periodo: Number(periodo) } : {}), ...(curso ? { curso: Number(curso) } : {}), ...(materia ? { materia: Number(materia) } : {}) }
    consulta.current?.abort()
    const controller = new AbortController(); consulta.current = controller
    setError(''); setCargando(true)
    try { const response = await resumenAnalitica(filtros, controller.signal); if (!controller.signal.aborted) { setDatos(response.data); setAplicados(filtros) } }
    catch (e) { if (!controller.signal.aborted) { setDatos(null); setAplicados(null); setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para consultar analítica.' : 'No fue posible consultar la analítica.') } }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }
  const exportar = async (formato: 'CSV' | 'PDF') => {
    if (!aplicados) return
    exportacion.current?.abort()
    const controller = new AbortController(); exportacion.current = controller
    try {
      const { data } = await exportarAnalitica(aplicados, formato, controller.signal)
      if (controller.signal.aborted) return
      const url = URL.createObjectURL(data as Blob); const link = document.createElement('a')
      link.href = url; link.download = `analitica.${formato.toLowerCase()}`; link.click(); URL.revokeObjectURL(url); onExportado()
    } catch (e) { if (!controller.signal.aborted) setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para exportar.' : 'No se pudo exportar la analítica.') }
  }
  const cambiarUnidad = (v: string) => { limpiarResultado(); setUnidad(v); setCalendario(''); setPeriodo(''); setCurso(''); setMateria(''); if (v !== unidad) { setCalendarios([]); setCursos([]) } setPeriodos([]); setMaterias([]) }
  const limpiar = () => { cambiarUnidad(alcance?.unidad_id ? String(alcance.unidad_id) : ''); setError('') }
  const metricas: Array<[string, string]> = [['matricula_actual', 'Matrícula actual'], ['promedio_general', 'Promedio general'], ['porcentaje_aprobacion', 'Aprobación (%)'], ['porcentaje_asistencia', 'Asistencia (%)'], ['incidentes_total', 'Incidentes']]
  return <section className="mb-6 rounded-2xl bg-white p-4 shadow-sm" aria-labelledby="analitica-titulo">
    <h2 id="analitica-titulo" className="text-lg font-semibold">{modo === 'voz' ? 'Contexto para reportes por voz' : 'Analítica'}</h2>
    <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Selector label="Unidad educativa" value={unidad} disabled={alcance?.tipo === 'UNIDAD'} onChange={cambiarUnidad} opciones={unidades.map(x => ({ id: x.id, nombre: x.nombre }))} />
      <Selector label="Gestión" value={calendario} onChange={v => { limpiarResultado(); setCalendario(v); setPeriodo(''); setPeriodos([]) }} opciones={calendarios.map(x => ({ id: x.id, nombre: String(x.año) }))} />
      <Selector label="Periodo" value={periodo} onChange={v => { limpiarResultado(); setPeriodo(v) }} opciones={periodos} />
      <Selector label="Curso" value={curso} onChange={v => { limpiarResultado(); setCurso(v); setMateria(''); setMaterias([]) }} opciones={cursos} />
      <Selector label="Materia" value={materia} onChange={v => { limpiarResultado(); setMateria(v) }} opciones={materias.map(x => ({ id: x.materia, nombre: x.materia_nombre }))} />
    </div>
    {modo === 'analitica' && <div className="mt-3 flex flex-wrap gap-2"><button type="button" className="btn-primary" onClick={() => void aplicar()} disabled={cargando}>Aplicar / actualizar</button><button type="button" className="rounded border px-3 py-2" onClick={limpiar}>Limpiar</button><button type="button" className="rounded border px-3 py-2" disabled={!aplicados} onClick={() => void exportar('CSV')}>Exportar CSV</button><button type="button" className="rounded border px-3 py-2" disabled={!aplicados} onClick={() => void exportar('PDF')}>Exportar PDF</button></div>}
    {modo === 'voz' && <VozPanel contexto={{ ...(unidad ? { unidad_educativa: Number(unidad) } : {}), ...(calendario ? { calendario_academico: Number(calendario) } : {}), ...(periodo ? { periodo: Number(periodo) } : {}), ...(curso ? { curso: Number(curso) } : {}), ...(materia ? { materia: Number(materia) } : {}) }} onExportado={onExportado} />}
    {cargando && <p role="status">Cargando analítica…</p>}{error && <p role="alert" className="text-red-700">{error}</p>}
    {datos && <><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{metricas.map(([key, label]) => <article key={key} className="rounded border p-3"><h3 className="font-medium">{label}</h3><p>{datos.indicadores[key] ?? 'Sin datos'}</p>{key === 'matricula_actual' && <p className="text-sm">Dato actual</p>}</article>)}</div>
      <p className="mt-3 text-sm">{datos.metadatos.matricula_actual.advertencia}</p>
      <p className="mt-1 text-sm">{datos.metadatos.incidentes.advertencia} El filtro de materia no aplica a matrícula ni incidentes. Rendimiento y asistencia aplican gestión, periodo, curso y materia cuando se seleccionan. La asistencia es el porcentaje de registros presentes.</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">{Object.entries(datos.series).map(([nombre, valores]) => <Grafico key={nombre} nombre={nombre} valores={valores} error={datos.metadatos.errores_parciales?.find(item => item.componente === nombre)?.mensaje} />)}</div>
      <p className="mt-3 text-sm">{datos.metadatos.metricas_omitidas.join(' ')}</p></>}
  </section>
}

function Grafico({ nombre, valores, error }: { nombre: string; valores: Array<{ etiqueta: string; valor: number }> | null; error?: string }) {
  const maximo = Math.max(1, ...(valores ?? []).map(v => v.valor))
  return <section className="rounded border p-3"><h3 className="font-semibold">{nombre.replaceAll('_', ' ')}</h3>{valores === null ? <p role="alert" className="text-red-700">{error ?? 'Serie no disponible.'}</p> : valores.length ? <><div aria-hidden="true" className="mt-2 space-y-1">{valores.map((v, i) => <div key={i} className="h-2 rounded bg-slate-100"><div className="h-2 rounded bg-brand-700" style={{ width: `${100 * v.valor / maximo}%` }} /></div>)}</div><table className="mt-2 w-full text-sm"><thead><tr><th className="text-left">Categoría</th><th className="text-right">Valor</th></tr></thead><tbody>{valores.map((v, i) => <tr key={`${v.etiqueta}-${i}`}><td>{v.etiqueta}</td><td className="text-right">{v.valor}</td></tr>)}</tbody></table></> : <p>Sin datos</p>}</section>
}

function Selector({ label, value, opciones, onChange, disabled }: { label: string; value: string; opciones: Opcion[]; onChange: (value: string) => void; disabled?: boolean }) {
  return <label className="text-sm">{label}<select className="mt-1 w-full rounded border p-2" value={value} disabled={disabled} onChange={e => onChange(e.target.value)}><option value="">Seleccione</option>{opciones.map(item => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></label>
}

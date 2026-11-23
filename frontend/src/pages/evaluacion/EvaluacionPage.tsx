import axios from 'axios'
import { GraduationCap, Plus, Save } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { listarAsignaciones, type AsignacionDocente } from '../../api/asignacionesDocentes'
import {
  crearActividad, listarDimensiones, listarPeriodos, obtenerGrilla,
  guardarCalificacionesActividad, type ActividadEvaluacion, type DimensionEvaluacion,
  type Grilla, type Periodo,
} from '../../api/evaluacion'
import { useAuth } from '../../app/contexts/AuthContext'

const formularioInicial = { nombre: '', fecha: '', puntaje_maximo: '100', dimension: '' }

export default function EvaluacionPage() {
  const { isProfesor } = useAuth()
  const puedeEditar = isProfesor()

  const [asignaciones, setAsignaciones] = useState<AsignacionDocente[]>([])
  const [asignacionId, setAsignacionId] = useState('')
  const [periodos, setPeriodos] = useState<Periodo[]>([])
  const [periodoId, setPeriodoId] = useState('')
  const [dimensiones, setDimensiones] = useState<DimensionEvaluacion[]>([])
  const [grilla, setGrilla] = useState<Grilla | null>(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(formularioInicial)
  const [guardandoColumna, setGuardandoColumna] = useState<number | null>(null)
  const [ediciones, setEdiciones] = useState<Record<number, Record<number, string>>>({})

  const asignacion = asignaciones.find((a) => String(a.id) === asignacionId)

  useEffect(() => {
    listarAsignaciones({ tipo: 'MATERIA', page_size: 100 })
      .then(({ data }) => setAsignaciones(data.results))
      .catch(() => setError('No fue posible cargar sus materias asignadas.'))
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPeriodoId(''); setGrilla(null); setDimensiones([])
    if (!asignacion?.calendario_academico) { setPeriodos([]); return }
    listarPeriodos(asignacion.calendario_academico).then(setPeriodos).catch(() => setError('No fue posible cargar los periodos.'))
    listarDimensiones(asignacion.calendario_academico, asignacion.nivel_educativo)
      .then(setDimensiones)
      .catch(() => setError('No existe una configuración de evaluación (HU-15) para este nivel y gestión.'))
  }, [asignacion])

  const cargarGrilla = useCallback(async () => {
    if (!asignacionId || !periodoId) return
    setCargando(true); setError('')
    try {
      const { data } = await obtenerGrilla(Number(asignacionId), Number(periodoId))
      setGrilla(data); setEdiciones({})
    } catch (e) {
      setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para consultar esta carga académica.' : 'No fue posible cargar el cuaderno pedagógico.')
    } finally { setCargando(false) }
  }, [asignacionId, periodoId])
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargarGrilla() }, [cargarGrilla])

  const crear = async () => {
    if (!asignacionId || !periodoId || !form.dimension) return
    setError(''); setExito('')
    try {
      await crearActividad({
        asignacion_docente: Number(asignacionId), periodo: Number(periodoId),
        dimension: Number(form.dimension), nombre: form.nombre, fecha: form.fecha,
        puntaje_maximo: form.puntaje_maximo,
      })
      setModal(false); setForm(formularioInicial); setExito('Actividad creada.')
      await cargarGrilla()
    } catch (e) {
      const respuesta = axios.isAxiosError(e) ? e.response : undefined
      setError(respuesta?.status === 403 ? 'No tiene permiso para crear actividades en esta asignación.' : mensajeDominio(respuesta?.data))
    }
  }

  const editarCelda = (actividadId: number, historialId: number, valor: string) =>
    setEdiciones((previas) => ({ ...previas, [actividadId]: { ...previas[actividadId], [historialId]: valor } }))

  const valorCelda = (actividadId: number, historialId: number | null, original: string | null) => {
    if (historialId !== null && ediciones[actividadId]?.[historialId] !== undefined) return ediciones[actividadId][historialId]
    return original ?? ''
  }

  const guardarColumna = async (actividad: ActividadEvaluacion) => {
    if (!grilla) return
    const cambios = ediciones[actividad.id]
    if (!cambios || Object.keys(cambios).length === 0) return
    setGuardandoColumna(actividad.id); setError(''); setExito('')
    try {
      await guardarCalificacionesActividad(
        actividad.id,
        Object.entries(cambios)
          .filter(([, valor]) => valor !== '')
          .map(([historialId, valor]) => ({ historial_inscripcion: Number(historialId), valor })),
      )
      setExito(`Notas de "${actividad.nombre}" guardadas.`)
      await cargarGrilla()
    } catch (e) {
      const respuesta = axios.isAxiosError(e) ? e.response : undefined
      setError(respuesta?.status === 403 ? 'No tiene permiso para calificar esta actividad.' : mensajeDominio(respuesta?.data))
    } finally { setGuardandoColumna(null) }
  }

  return <section className="p-4 sm:p-6 lg:p-8" aria-labelledby="evaluacion-titulo">
    <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div><div className="flex items-center gap-3"><GraduationCap className="text-purple-700" /><h1 id="evaluacion-titulo" className="text-2xl font-bold">Evaluación y calificaciones</h1></div>
        <p className="mt-1 text-sm text-slate-500">Cuaderno pedagógico: actividades por dimensión y promedio trimestral (HU-16 / HU-17).</p></div>
      {puedeEditar && asignacionId && periodoId && <button className="btn-primary" onClick={() => setModal(true)}><Plus size={18} />Nueva actividad</button>}
    </header>

    <div className="mb-5 grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-2">
      <Select label="Materia asignada" value={asignacionId} onChange={setAsignacionId}
        opciones={[['', 'Seleccione'], ...asignaciones.map((a) => [String(a.id), `${a.materia_nombre} - ${a.curso_nombre}`])]} />
      <Select label="Periodo (trimestre)" value={periodoId} onChange={setPeriodoId}
        opciones={[['', 'Seleccione'], ...periodos.map((p) => [String(p.id), p.nombre])]} />
    </div>

    {exito && <p role="status" className="mb-4 rounded-xl bg-emerald-50 p-3 text-emerald-700">{exito}</p>}
    {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}

    {cargando && <p className="p-8 text-center text-slate-500">Cargando cuaderno pedagógico...</p>}

    {!cargando && grilla && <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-3">Estudiante</th>
            {grilla.actividades.map((actividad) => <th key={actividad.id} className="px-4 py-3">
              <div className="text-xs font-semibold uppercase text-slate-400">{actividad.dimension_codigo}</div>
              <div>{actividad.nombre}</div>
              <div className="text-xs text-slate-500">/ {actividad.puntaje_maximo}</div>
              {puedeEditar && <button className="mt-1 flex items-center gap-1 text-xs text-brand-700" disabled={guardandoColumna === actividad.id} onClick={() => void guardarColumna(actividad)}>
                <Save size={14} />{guardandoColumna === actividad.id ? 'Guardando...' : 'Guardar'}
              </button>}
            </th>)}
            <th className="px-4 py-3">Promedio trimestral</th>
          </tr>
        </thead>
        <tbody>
          {grilla.estudiantes.map((fila) => <tr key={fila.estudiante} className="border-t border-slate-100">
            <td className="px-4 py-3">{fila.estudiante_nombre}</td>
            {grilla.actividades.map((actividad) => <td key={actividad.id} className="px-4 py-3">
              {puedeEditar && fila.historial_inscripcion !== null ? (
                <input
                  aria-label={`Nota de ${fila.estudiante_nombre} en ${actividad.nombre}`}
                  type="number" min={0} max={Number(actividad.puntaje_maximo)} step="0.01"
                  value={valorCelda(actividad.id, fila.historial_inscripcion, fila.notas[actividad.id])}
                  onChange={(e) => editarCelda(actividad.id, fila.historial_inscripcion as number, e.target.value)}
                  className="w-20 rounded-lg border border-slate-300 px-2 py-1"
                />
              ) : (fila.notas[actividad.id] ?? '—')}
            </td>)}
            <td className="px-4 py-3 font-semibold">
              {fila.resultado_trimestral ?? '—'}
              {fila.condicion && <span className={`ml-2 text-xs ${fila.condicion === 'APROBADO' ? 'text-emerald-700' : 'text-red-600'}`}>({fila.condicion})</span>}
            </td>
          </tr>)}
        </tbody>
      </table>
    </div>}

    {modal && <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6">
        <h2 className="text-xl font-bold">Nueva actividad evaluativa</h2>
        <div className="mt-5 grid gap-4">
          <Campo label="Nombre" value={form.nombre} onChange={(v) => setForm({ ...form, nombre: v })} />
          <Campo label="Fecha" type="date" value={form.fecha} onChange={(v) => setForm({ ...form, fecha: v })} />
          <Campo label="Puntaje máximo" type="number" value={form.puntaje_maximo} onChange={(v) => setForm({ ...form, puntaje_maximo: v })} />
          <Select label="Dimensión" value={form.dimension} onChange={(v) => setForm({ ...form, dimension: v })}
            opciones={[['', 'Seleccione'], ...dimensiones.map((d) => [String(d.id), `${d.nombre} (${d.ponderacion} pts)`])]} />
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button className="btn-secondary" onClick={() => setModal(false)}>Cancelar</button>
          <button className="btn-primary" onClick={() => void crear()}>Guardar</button>
        </div>
      </div>
    </div>}
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

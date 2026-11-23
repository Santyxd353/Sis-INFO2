import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Settings } from 'lucide-react'
import axios from '../../api/axiosInstance'

interface Curso { id: number; nombre: string }
interface Alerta {
  estudiante: number
  nombre?: string
  apellido?: string
  curso?: string | null
  promedio?: string | number | null
  porcentaje_faltas: string | number
  nivel?: string | null
  nivel_display?: string | null
  tipos: string[]
  motivos: string[]
  umbral_rendimiento: string | number
  umbral_inasistencia: string | number
}
interface DetalleAlerta extends Alerta {
  asistencia: {
    total: number; presentes: number; ausentes: number
    tardes: number; licencias: number; porcentaje_faltas: number
  }
  notas: { id: number; materia_nombre?: string; tipo_display?: string; nota: string | number }[]
}
interface Config {
  id?: number
  umbral_rendimiento: string | number
  umbral_riesgo_alto: string | number
  umbral_inasistencia: string | number
  porcentaje_minimo_asistencia: string | number
}

const colores: Record<string, string> = {
  B: 'bg-green-100 text-green-800',
  M: 'bg-yellow-100 text-yellow-800',
  A: 'bg-red-100 text-red-800',
}

export default function RiesgoAcademico() {
  const [cursos, setCursos] = useState<Curso[]>([])
  const [alertas, setAlertas] = useState<Alerta[]>([])
  const [curso, setCurso] = useState('')
  const [nivel, setNivel] = useState('')
  const [tipo, setTipo] = useState('')
  const [detalle, setDetalle] = useState<DetalleAlerta | null>(null)
  const [config, setConfig] = useState<Config | null>(null)
  const [mostrarConfig, setMostrarConfig] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)

  useEffect(() => {
    axios.get('/academico/cursos/').then((res) => setCursos(res.data.results ?? res.data))
    axios.get('/seguimiento/configuracion/').then((res) => {
      const lista = res.data.results ?? res.data
      if (lista.length) setConfig(lista[0])
    })
  }, [])

  const cargar = useCallback(() => {
    const params = new URLSearchParams()
    if (curso) params.set('curso', curso)
    if (nivel) params.set('nivel', nivel)
    if (tipo) params.set('tipo', tipo)
    axios.get('/seguimiento/alertas/?' + params.toString())
      .then((res) => setAlertas(res.data.results ?? res.data))
  }, [curso, nivel, tipo])

  useEffect(() => { cargar() }, [cargar])

  const verDetalle = async (estudiante: number) => {
    const res = await axios.get(`/seguimiento/alertas/${estudiante}/`)
    setDetalle(res.data)
  }

  const guardarConfig = async () => {
    if (!config) return
    setAviso(null)
    try {
      if (config.id) {
        await axios.put(`/seguimiento/configuracion/${config.id}/`, config)
      } else {
        const res = await axios.post('/seguimiento/configuracion/', config)
        setConfig(res.data)
      }
      setAviso('Umbrales actualizados')
      setMostrarConfig(false)
    } catch {
      setAviso('No se pudieron guardar los umbrales')
    }
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <AlertTriangle /> Riesgo académico
        </h1>
        <button
          onClick={() => setMostrarConfig((v) => !v)}
          className="flex items-center gap-2 rounded border px-3 py-2 text-sm hover:bg-gray-50"
        >
          <Settings size={16} /> Configurar umbrales
        </button>
      </div>

      {aviso && <div className="rounded bg-brand-50 p-3 text-sm text-brand-800">{aviso}</div>}

      {mostrarConfig && config && (
        <div className="grid gap-4 rounded border p-4 md:grid-cols-4">
          {(['umbral_rendimiento', 'umbral_riesgo_alto', 'umbral_inasistencia', 'porcentaje_minimo_asistencia'] as const).map((k) => (
            <label key={k} className="block text-sm font-medium capitalize">
              {k.replace(/_/g, ' ')}
              <input
                type="number"
                step="0.01"
                value={config[k]}
                onChange={(e) => setConfig({ ...config, [k]: e.target.value })}
                className="mt-1 w-full rounded border p-2"
              />
            </label>
          ))}
          <button onClick={guardarConfig} className="rounded bg-brand-600 px-4 py-2 text-white hover:bg-brand-700 md:col-span-4">
            Guardar umbrales
          </button>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <label className="block text-sm font-medium">
          Curso
          <select value={curso} onChange={(e) => setCurso(e.target.value)} className="mt-1 w-full rounded border p-2">
            <option value="">Todos</option>
            {cursos.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <label className="block text-sm font-medium">
          Tipo de riesgo
          <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="mt-1 w-full rounded border p-2">
            <option value="">Todos</option>
            <option value="rendimiento">Bajo rendimiento</option>
            <option value="inasistencia">Inasistencia recurrente</option>
          </select>
        </label>
        <label className="block text-sm font-medium">
          Nivel
          <select value={nivel} onChange={(e) => setNivel(e.target.value)} className="mt-1 w-full rounded border p-2">
            <option value="">Todos</option>
            <option value="A">Alto</option>
            <option value="M">Medio</option>
            <option value="B">Bajo</option>
          </select>
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {alertas.map((a) => (
          <button
            key={a.estudiante}
            onClick={() => verDetalle(a.estudiante)}
            className="rounded border p-4 text-left shadow-sm hover:border-brand-400"
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold">{a.apellido} {a.nombre}</span>
              <span className={'rounded px-2 py-1 text-xs ' + (colores[a.nivel || ''] || '')}>
                {a.nivel_display || '-'}
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-500">{a.curso}</p>
            <p className="mt-2 text-sm">Promedio: {a.promedio ?? '-'} · Faltas: {a.porcentaje_faltas}%</p>
            <ul className="mt-2 list-disc pl-4 text-xs text-gray-600">
              {a.motivos.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          </button>
        ))}
        {alertas.length === 0 && <p className="text-sm text-gray-500">Sin alertas para los filtros seleccionados.</p>}
      </div>

      {detalle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setDetalle(null)}>
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded bg-white p-6" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">Detalle de alerta: {detalle.apellido} {detalle.nombre}</h2>
              <button onClick={() => setDetalle(null)} className="text-gray-500 hover:text-gray-800">Cerrar</button>
            </div>
            <p className="text-sm text-gray-600">Curso: {detalle.curso}</p>
            <p className="text-sm text-gray-600">Promedio: {detalle.promedio ?? '-'} (umbral {detalle.umbral_rendimiento})</p>
            <p className="text-sm text-gray-600">Faltas: {detalle.porcentaje_faltas}% (umbral {detalle.umbral_inasistencia}%)</p>

            <h3 className="mt-4 font-semibold">Asistencia</h3>
            <p className="text-sm">
              Total {detalle.asistencia.total} · Presentes {detalle.asistencia.presentes} ·
              Ausentes {detalle.asistencia.ausentes} · Atrasos {detalle.asistencia.tardes} ·
              Licencias {detalle.asistencia.licencias}
            </p>

            <h3 className="mt-4 font-semibold">Notas</h3>
            <table className="min-w-full text-sm">
              <tbody>
                {detalle.notas.map((n) => (
                  <tr key={n.id} className="border-b last:border-0">
                    <td className="py-1">{n.materia_nombre}</td>
                    <td className="py-1">{n.tipo_display}</td>
                    <td className="py-1">{n.nota}</td>
                  </tr>
                ))}
                {detalle.notas.length === 0 && (
                  <tr><td className="py-1 text-gray-500">Sin notas registradas.</td></tr>
                )}
              </tbody>
            </table>

            <h3 className="mt-4 font-semibold">Motivos</h3>
            <ul className="list-disc pl-5 text-sm text-gray-600">
              {detalle.motivos.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

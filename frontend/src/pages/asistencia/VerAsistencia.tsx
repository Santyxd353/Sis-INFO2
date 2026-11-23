import { Fragment, useCallback, useEffect, useState } from 'react'
import axios from '../../api/axiosInstance'

interface Curso { id: number; nombre: string }
interface Registro {
  id: number
  fecha: string
  curso?: number
  curso_nombre?: string
  materia_nombre?: string
  asignacion_display?: string
  docente_nombre?: string
  observacion?: string
}
interface Detalle {
  id: number
  estudiante_nombre?: string
  estudiante_apellido?: string
  estado: string
  estado_display?: string
  observacion?: string
}

const ETIQUETA: Record<string, string> = { P: 'Presente', A: 'Ausente', T: 'Atraso', L: 'Licencia' }
const COLOR: Record<string, string> = {
  P: 'bg-green-100 text-green-800',
  A: 'bg-red-100 text-red-800',
  T: 'bg-yellow-100 text-yellow-800',
  L: 'bg-brand-100 text-brand-800',
}

export default function VerAsistencia() {
  const [cursos, setCursos] = useState<Curso[]>([])
  const [registros, setRegistros] = useState<Registro[]>([])
  const [curso, setCurso] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [abierto, setAbierto] = useState<number | null>(null)
  const [detalles, setDetalles] = useState<Detalle[]>([])

  useEffect(() => {
    axios.get('/academico/cursos/').then((res) => setCursos(res.data.results ?? res.data))
  }, [])

  const cargar = useCallback(() => {
    const params = new URLSearchParams()
    if (curso) params.set('curso', curso)
    if (desde) params.set('desde', desde)
    if (hasta) params.set('hasta', hasta)
    axios.get('/asistencia/registros/?' + params.toString())
      .then((res) => setRegistros(res.data.results ?? res.data))
  }, [curso, desde, hasta])

  useEffect(() => { cargar() }, [cargar])

  const verDetalle = async (id: number) => {
    if (abierto === id) { setAbierto(null); return }
    const res = await axios.get('/asistencia/detalles/?registro=' + id)
    setDetalles(res.data.results ?? res.data)
    setAbierto(id)
  }

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-bold">Consulta de asistencia</h1>

      <div className="grid gap-4 md:grid-cols-4">
        <label className="block text-sm font-medium">
          Curso
          <select value={curso} onChange={(e) => setCurso(e.target.value)} className="mt-1 w-full rounded border p-2">
            <option value="">Todos</option>
            {cursos.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <label className="block text-sm font-medium">
          Desde
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="mt-1 w-full rounded border p-2" />
        </label>
        <label className="block text-sm font-medium">
          Hasta
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="mt-1 w-full rounded border p-2" />
        </label>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase">Fecha</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase">Curso</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase">Asignación</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase">Docente</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {registros.map((r) => (
              <Fragment key={r.id}>
                <tr>
                  <td className="px-4 py-2">{r.fecha}</td>
                  <td className="px-4 py-2">{r.curso_nombre || r.curso}</td>
                  <td className="px-4 py-2">{r.materia_nombre || r.asignacion_display || '-'}</td>
                  <td className="px-4 py-2">{r.docente_nombre || '-'}</td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => verDetalle(r.id)} className="text-sm text-brand-600 hover:underline">
                      {abierto === r.id ? 'Ocultar' : 'Ver detalle'}
                    </button>
                  </td>
                </tr>
                {abierto === r.id && (
                  <tr>
                    <td colSpan={5} className="bg-gray-50 px-4 py-3">
                      {r.observacion && <p className="mb-2 text-sm text-gray-600">Observación: {r.observacion}</p>}
                      <table className="min-w-full text-sm">
                        <tbody>
                          {detalles.map((d) => (
                            <tr key={d.id} className="border-b last:border-0">
                              <td className="py-1">{d.estudiante_apellido} {d.estudiante_nombre}</td>
                              <td className="py-1">
                                <span className={'rounded px-2 py-0.5 text-xs ' + (COLOR[d.estado] || '')}>
                                  {d.estado_display || ETIQUETA[d.estado] || d.estado}
                                </span>
                              </td>
                              <td className="py-1 text-gray-500">{d.observacion}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

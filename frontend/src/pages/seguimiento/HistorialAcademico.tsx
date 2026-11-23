import { Fragment, useCallback, useEffect, useState } from 'react'
import axios from '../../api/axiosInstance'

interface Curso { id: number; nombre: string }
interface Nota {
  id: number
  materia_nombre?: string
  tipo_display?: string
  nota: string | number
  ponderacion: string | number
}
interface Historial {
  id: number
  estudiante_nombre?: string
  estudiante_apellido?: string
  periodo_nombre?: string
  gestion?: number
  curso_nombre?: string
  promedio?: string | number | null
  observaciones?: string
  notas?: Nota[]
}

export default function HistorialAcademico() {
  const [cursos, setCursos] = useState<Curso[]>([])
  const [curso, setCurso] = useState('')
  const [gestion, setGestion] = useState('')
  const [historial, setHistorial] = useState<Historial[]>([])
  const [abierto, setAbierto] = useState<number | null>(null)

  useEffect(() => {
    axios.get('/academico/cursos/').then((res) => setCursos(res.data.results ?? res.data))
  }, [])

  const cargar = useCallback(() => {
    const params = new URLSearchParams()
    if (curso) params.set('curso', curso)
    if (gestion) params.set('gestion', gestion)
    axios.get('/seguimiento/historial/?' + params.toString())
      .then((res) => setHistorial(res.data.results ?? res.data))
  }, [curso, gestion])

  useEffect(() => { cargar() }, [cargar])

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-bold">Historial académico</h1>

      <div className="grid gap-4 md:grid-cols-3">
        <label className="block text-sm font-medium">
          Curso
          <select value={curso} onChange={(e) => setCurso(e.target.value)} className="mt-1 w-full rounded border p-2">
            <option value="">Todos</option>
            {cursos.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <label className="block text-sm font-medium">
          Gestión (año)
          <input
            type="number"
            value={gestion}
            onChange={(e) => setGestion(e.target.value)}
            placeholder="Ej. 2026"
            className="mt-1 w-full rounded border p-2"
          />
        </label>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase">Estudiante</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase">Gestión</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase">Periodo</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase">Curso</th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase">Promedio</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {historial.map((h) => (
              <Fragment key={h.id}>
                <tr>
                  <td className="px-4 py-2">{h.estudiante_apellido} {h.estudiante_nombre}</td>
                  <td className="px-4 py-2">{h.gestion ?? '-'}</td>
                  <td className="px-4 py-2">{h.periodo_nombre ?? '-'}</td>
                  <td className="px-4 py-2">{h.curso_nombre}</td>
                  <td className="px-4 py-2">{h.promedio ?? '-'}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => setAbierto(abierto === h.id ? null : h.id)}
                      className="text-sm text-brand-600 hover:underline"
                    >
                      {abierto === h.id ? 'Ocultar notas' : 'Ver notas'}
                    </button>
                  </td>
                </tr>
                {abierto === h.id && (
                  <tr>
                    <td colSpan={6} className="bg-gray-50 px-4 py-3">
                      {h.observaciones && <p className="mb-2 text-sm text-gray-600">{h.observaciones}</p>}
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr className="text-left text-xs uppercase text-gray-500">
                            <th className="py-1">Materia</th>
                            <th className="py-1">Evaluación</th>
                            <th className="py-1">Nota</th>
                            <th className="py-1">Ponderación</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(h.notas ?? []).map((n) => (
                            <tr key={n.id} className="border-b last:border-0">
                              <td className="py-1">{n.materia_nombre}</td>
                              <td className="py-1">{n.tipo_display}</td>
                              <td className="py-1">{n.nota}</td>
                              <td className="py-1">{n.ponderacion}</td>
                            </tr>
                          ))}
                          {(!h.notas || h.notas.length === 0) && (
                            <tr><td colSpan={4} className="py-1 text-gray-500">Sin notas registradas.</td></tr>
                          )}
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

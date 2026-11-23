import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { CheckCircle, User } from 'lucide-react'
import axios from '../../api/axiosInstance'

interface Curso { id: number; nombre: string; paralelo?: { letra?: string } }
interface Asignacion { id: number; curso: number; materia_nombre?: string; curso_nombre?: string }
interface EstudianteFila {
  estudiante: number
  nombre: string
  apellido: string
  rude?: string | null
  estado?: string | null
  observacion?: string
}

const ESTADOS = [
  { value: 'P', label: 'Presente' },
  { value: 'A', label: 'Ausente' },
  { value: 'T', label: 'Atraso' },
  { value: 'L', label: 'Licencia' },
]

export default function RegistrarAsistencia() {
  const [cursos, setCursos] = useState<Curso[]>([])
  const [asignaciones, setAsignaciones] = useState<Asignacion[]>([])
  const [curso, setCurso] = useState('')
  const [asignacion, setAsignacion] = useState('')
  const [fecha, setFecha] = useState(() => new Date().toISOString().split('T')[0])
  const [observacion, setObservacion] = useState('')
  const [estudiantes, setEstudiantes] = useState<EstudianteFila[]>([])
  const [detalles, setDetalles] = useState<Record<number, string>>({})
  const [observaciones, setObservaciones] = useState<Record<number, string>>({})
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    axios.get('/academico/cursos/').then((res) => setCursos(res.data.results ?? res.data))
  }, [])

  const cargarEstudiantes = (asignacionId: string, fechaVal: string) => {
    axios.get(`/asistencia/registros/estudiantes/?asignacion=${asignacionId}&fecha=${fechaVal}`).then((res) => {
      const lista: EstudianteFila[] = res.data.results ?? res.data
      setEstudiantes(lista)
      const est: Record<number, string> = {}
      const obs: Record<number, string> = {}
      lista.forEach((e) => {
        est[e.estudiante] = e.estado || 'P'
        obs[e.estudiante] = e.observacion || ''
      })
      setDetalles(est)
      setObservaciones(obs)
    })
  }

  const cambiarCurso = (valor: string) => {
    setCurso(valor)
    setAsignaciones([])
    setAsignacion('')
    setEstudiantes([])
    if (valor) {
      axios.get('/academico/materias-curso/?curso=' + valor)
        .then((res) => setAsignaciones(res.data.results ?? res.data))
    }
  }

  const cambiarAsignacion = (valor: string) => {
    setAsignacion(valor)
    if (valor) {
      cargarEstudiantes(valor, fecha)
    } else {
      setEstudiantes([])
      setDetalles({})
      setObservaciones({})
    }
  }

  const cambiarFecha = (valor: string) => {
    setFecha(valor)
    if (asignacion) cargarEstudiantes(asignacion, valor)
  }

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    setMensaje(null)
    setError(null)
    try {
      await axios.post('/asistencia/registros/registrar/', {
        asignacion,
        fecha,
        observacion,
        detalles: estudiantes.map((est) => ({
          estudiante: est.estudiante,
          estado: detalles[est.estudiante] || 'P',
          observacion: observaciones[est.estudiante] || '',
        })),
      })
      setMensaje('Asistencia registrada correctamente')
    } catch {
      setError('Error al registrar asistencia')
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">Registrar asistencia</h1>
      {mensaje && <div className="rounded bg-green-50 p-3 text-sm text-green-800">{mensaje}</div>}
      {error && <div className="rounded bg-red-50 p-3 text-sm text-red-800">{error}</div>}

      <div className="grid gap-4 md:grid-cols-3">
        <label className="block text-sm font-medium">
          Curso y paralelo
          <select value={curso} onChange={(e) => cambiarCurso(e.target.value)} className="mt-1 w-full rounded border p-2" required>
            <option value="">Seleccione...</option>
            {cursos.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}{c.paralelo?.letra ? ` - Paralelo ${c.paralelo.letra}` : ''}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm font-medium">
          Asignación (materia)
          <select
            value={asignacion}
            onChange={(e) => cambiarAsignacion(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
            disabled={!curso}
          >
            <option value="">Seleccione...</option>
            {asignaciones.map((a) => (
              <option key={a.id} value={a.id}>{a.materia_nombre}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm font-medium">
          Fecha
          <input type="date" value={fecha} onChange={(e) => cambiarFecha(e.target.value)} className="mt-1 w-full rounded border p-2" required />
        </label>
      </div>

      <label className="block text-sm font-medium">
        Observación general del registro
        <input
          type="text"
          value={observacion}
          onChange={(e) => setObservacion(e.target.value)}
          placeholder="Opcional"
          className="mt-1 w-full rounded border p-2"
        />
      </label>

      {asignacion && estudiantes.length === 0 && (
        <p className="text-sm text-gray-500">No hay estudiantes inscritos en este curso.</p>
      )}

      <div className="space-y-3">
        {estudiantes.map((est) => (
          <div key={est.estudiante} className="grid gap-3 rounded border p-3 md:grid-cols-[1fr_180px_1fr] md:items-center">
            <div className="flex items-center gap-2">
              <User size={18} />
              <span>{est.apellido} {est.nombre}</span>
              {est.rude && <span className="text-xs text-gray-400">RUDE {est.rude}</span>}
            </div>
            <select
              value={detalles[est.estudiante] || 'P'}
              onChange={(ev) => setDetalles((d) => ({ ...d, [est.estudiante]: ev.target.value }))}
              className="rounded border p-1"
            >
              {ESTADOS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <input
              type="text"
              value={observaciones[est.estudiante] || ''}
              onChange={(ev) => setObservaciones((o) => ({ ...o, [est.estudiante]: ev.target.value }))}
              placeholder="Observación del estudiante"
              className="rounded border p-1 text-sm"
            />
          </div>
        ))}
      </div>

      <button
        type="submit"
        disabled={!asignacion}
        className="flex items-center gap-2 rounded bg-brand-600 px-4 py-2 text-white hover:bg-brand-700 disabled:opacity-50"
      >
        <CheckCircle size={18} /> Guardar asistencia
      </button>
    </form>
  )
}

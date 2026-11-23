import { BookOpen } from 'lucide-react'
import { useEffect, useState } from 'react'
import axios from '../../../api/axiosInstance'
import type { CursoSeleccionado } from '../types'

interface Unidad {
  id: number
  nombre: string
}

interface Grado {
  id: number
  nombre: string
}

interface Paralelo {
  id: number
  letra: string
}

interface Curso {
  id: number
  paralelo_id?: number
  nombre: string
  tutor?: { usuario?: { nombre?: string; apellido?: string } } | number | null
}

interface RespuestaPaginada<T> {
  results: T[]
}

interface Props {
  curso: CursoSeleccionado | null
  rude: string
  onSelect: (curso: CursoSeleccionado) => void
  onRudeChange: (rude: string) => void
}

const lista = <T,>(data: T[] | RespuestaPaginada<T>) =>
  Array.isArray(data) ? data : data.results ?? []

export default function PasoSeleccionarCurso({
  curso,
  rude,
  onSelect,
  onRudeChange,
}: Props) {
  const [unidades, setUnidades] = useState<Unidad[]>([])
  const [grados, setGrados] = useState<Grado[]>([])
  const [paralelos, setParalelos] = useState<Paralelo[]>([])
  const [cursos, setCursos] = useState<Curso[]>([])
  const [unidadId, setUnidadId] = useState<number | null>(curso?.unidad_id ?? null)
  const [gradoId, setGradoId] = useState<number | null>(null)
  const [paraleloId, setParaleloId] = useState<number | null>(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let activo = true
    axios
      .get<Unidad[] | RespuestaPaginada<Unidad>>('/institucion/unidades-educativas/')
      .then((response) => {
        if (activo) setUnidades(lista(response.data))
      })
      .catch(() => {
        if (activo) setError('No se pudieron cargar las unidades educativas.')
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [])

  useEffect(() => {
    if (!unidadId) return
    let activo = true
    axios
      .get<Grado[] | RespuestaPaginada<Grado>>(
        `/academico/grados/?unidad_educativa=${unidadId}`,
      )
      .then((response) => {
        if (activo) setGrados(lista(response.data))
      })
      .catch(() => {
        if (activo) setError('No se pudieron cargar los grados.')
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [unidadId])

  useEffect(() => {
    if (!gradoId) return
    let activo = true
    axios
      .get<Paralelo[] | RespuestaPaginada<Paralelo>>(`/academico/paralelos/?grado=${gradoId}`)
      .then((response) => {
        if (activo) setParalelos(lista(response.data))
      })
      .catch(() => {
        if (activo) setError('No se pudieron cargar los paralelos.')
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [gradoId])

  useEffect(() => {
    if (!paraleloId) return
    let activo = true
    axios
      .get<Curso[] | RespuestaPaginada<Curso>>(`/academico/cursos/?paralelo=${paraleloId}`)
      .then((response) => {
        if (activo) setCursos(lista(response.data))
      })
      .catch(() => {
        if (activo) {
          setCursos([])
          setError('No se pudieron cargar los cursos.')
        }
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [paraleloId])

  const cambiarUnidad = (valor: string) => {
    setCargando(Boolean(valor))
    setError(null)
    setUnidadId(valor ? Number(valor) : null)
    setGradoId(null)
    setParaleloId(null)
    setGrados([])
    setParalelos([])
    setCursos([])
  }

  const cambiarGrado = (valor: string) => {
    setCargando(Boolean(valor))
    setError(null)
    setGradoId(valor ? Number(valor) : null)
    setParaleloId(null)
    setParalelos([])
    setCursos([])
  }

  const cambiarParalelo = (id: number) => {
    setCargando(true)
    setError(null)
    setParaleloId(id)
    setCursos([])
  }

  const seleccionarCurso = (item: Curso) => {
    const unidad = unidades.find((actual) => actual.id === unidadId)
    const grado = grados.find((actual) => actual.id === gradoId)
    const paralelo = paralelos.find((actual) => actual.id === paraleloId)
    onSelect({
      curso_id: item.id ?? item.paralelo_id ?? paraleloId!,
      curso_nombre: item.nombre,
      grado: grado?.nombre ?? 'Desconocido',
      paralelo: paralelo?.letra ?? '—',
      unidad_id: unidadId!,
      unidad_nombre: unidad?.nombre ?? 'Desconocida',
    })
  }

  const tutorNombre = (item: Curso) => {
    if (!item.tutor || typeof item.tutor === 'number') return 'Sin asignar'
    const usuario = item.tutor.usuario
    return usuario ? `${usuario.nombre ?? ''} ${usuario.apellido ?? ''}`.trim() : 'Sin asignar'
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <label className="block text-sm font-medium text-slate-700">
        <span className="flex items-center gap-2">
          <BookOpen size={18} /> 1. Seleccionar unidad educativa
        </span>
        <select
          value={unidadId ?? ''}
          onChange={(event) => cambiarUnidad(event.target.value)}
          className="mt-3 w-full rounded-lg border border-slate-300 px-4 py-2"
        >
          <option value="">-- Seleccione una unidad --</option>
          {unidades.map((unidad) => (
            <option key={unidad.id} value={unidad.id}>
              {unidad.nombre}
            </option>
          ))}
        </select>
      </label>

      {unidadId && (
        <label className="block text-sm font-medium text-slate-700">
          2. Seleccionar grado
          <select
            value={gradoId ?? ''}
            onChange={(event) => cambiarGrado(event.target.value)}
            disabled={cargando}
            className="mt-3 w-full rounded-lg border border-slate-300 px-4 py-2 disabled:bg-slate-100"
          >
            <option value="">{cargando ? 'Cargando...' : '-- Seleccione un grado --'}</option>
            {grados.map((grado) => (
              <option key={grado.id} value={grado.id}>
                {grado.nombre}
              </option>
            ))}
          </select>
        </label>
      )}

      {gradoId && (
        <div>
          <p className="mb-3 text-sm font-medium text-slate-700">3. Seleccionar paralelo</p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {paralelos.map((paralelo) => (
              <button
                type="button"
                key={paralelo.id}
                onClick={() => cambiarParalelo(paralelo.id)}
                className={`rounded-lg border-2 p-3 font-medium transition-colors ${
                  paraleloId === paralelo.id
                    ? 'border-brand-600 bg-brand-50 text-brand-700'
                    : 'border-slate-300 text-slate-700 hover:border-brand-400'
                }`}
              >
                Paralelo {paralelo.letra}
              </button>
            ))}
          </div>
        </div>
      )}

      {paraleloId && (
        <div>
          <p className="mb-3 text-sm font-medium text-slate-700">4. Seleccionar curso</p>
          {cargando ? (
            <p className="text-slate-500">Cargando cursos...</p>
          ) : cursos.length === 0 ? (
            <p className="rounded-lg bg-yellow-50 p-4 text-yellow-800">
              No hay cursos disponibles en este paralelo.
            </p>
          ) : (
            <div className="space-y-3">
              {cursos.map((item) => {
                const id = item.id ?? item.paralelo_id
                return (
                  <button
                    type="button"
                    key={id}
                    onClick={() => seleccionarCurso(item)}
                    className={`block w-full rounded-lg border p-4 text-left transition-colors ${
                      curso?.curso_id === id
                        ? 'border-brand-500 bg-brand-50'
                        : 'border-slate-300 hover:border-brand-400 hover:bg-slate-50'
                    }`}
                  >
                    <span className="block font-medium text-slate-900">{item.nombre}</span>
                    <span className="block text-sm text-slate-600">Tutor: {tutorNombre(item)}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {paraleloId && (
        <label className="block rounded-lg border border-brand-200 bg-brand-50 p-4 text-sm font-medium text-slate-700">
          RUDE (Registro Único de Estudiante) *
          <input
            value={rude}
            onChange={(event) => onRudeChange(event.target.value)}
            placeholder="Ingrese el RUDE del estudiante"
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-4 py-2"
          />
          <span className="mt-2 block font-normal text-slate-600">
            El RUDE es obligatorio y debe ser único en el sistema.
          </span>
        </label>
      )}
    </div>
  )
}

import { Plus, Users } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { obtenerEstudiantes } from '../../../api/inscripcion'
import type {
  EstudianteApi,
  EstudianteSeleccionado,
} from '../types'

interface Props {
  estudiante: EstudianteSeleccionado | null
  onSelect: (estudiante: EstudianteSeleccionado) => void
}

const formularioInicial = {
  nombre: '',
  apellido: '',
  ci: '',
  email: '',
  sexo: 'M',
  username: '',
  password: '',
}

export default function PasoSeleccionarOCrearEstudiante({
  estudiante,
  onSelect,
}: Props) {
  const [tab, setTab] = useState<'existente' | 'nuevo'>('existente')
  const [estudiantes, setEstudiantes] = useState<EstudianteApi[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busqueda, setBusqueda] = useState('')
  const [formNuevo, setFormNuevo] = useState(formularioInicial)

  useEffect(() => {
    let activo = true
    obtenerEstudiantes()
      .then((datos) => {
        if (activo) setEstudiantes(datos)
      })
      .catch(() => {
        if (activo) setError('No se pudo cargar la lista de estudiantes.')
      })
      .finally(() => {
        if (activo) setCargando(false)
      })
    return () => {
      activo = false
    }
  }, [])

  const estudiantesFiltrados = useMemo(() => {
    const termino = busqueda.trim().toLowerCase()
    if (!termino) return estudiantes
    return estudiantes.filter((item) => {
      const nombre = `${item.usuario.nombre} ${item.usuario.apellido}`.toLowerCase()
      return nombre.includes(termino) || item.usuario.ci.toLowerCase().includes(termino)
    })
  }, [busqueda, estudiantes])

  const seleccionarExistente = (item: EstudianteApi) => {
    onSelect({
      usuario_id: item.usuario.id,
      estudiante_id: item.id || item.usuario.id,
      es_nuevo: false,
      datos: {
        nombre: item.usuario.nombre,
        apellido: item.usuario.apellido,
        ci: item.usuario.ci,
        email: item.usuario.email,
        sexo: item.usuario.sexo,
      },
    })
  }

  const seleccionarNuevo = () => {
    if (
      !formNuevo.nombre.trim() ||
      !formNuevo.apellido.trim() ||
      !formNuevo.ci.trim() ||
      !formNuevo.email.trim() ||
      !formNuevo.username.trim() ||
      !formNuevo.password
    ) {
      setError('Complete todos los campos obligatorios.')
      return
    }
    if (formNuevo.password.length < 8) {
      setError('La contraseña temporal debe tener al menos 8 caracteres.')
      return
    }
    setError(null)
    onSelect({
      es_nuevo: true,
      datos: {
        nombre: formNuevo.nombre.trim(),
        apellido: formNuevo.apellido.trim(),
        ci: formNuevo.ci.trim(),
        email: formNuevo.email.trim(),
        sexo: formNuevo.sexo,
        username: formNuevo.username.trim(),
        password: formNuevo.password,
      },
    })
  }

  const actualizarCampo = (campo: keyof typeof formularioInicial, valor: string) => {
    setFormNuevo((actual) => ({ ...actual, [campo]: valor }))
  }

  return (
    <div className="space-y-6">
      <div className="flex gap-3 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setTab('existente')}
          className={`flex items-center gap-2 border-b-2 px-3 pb-3 font-medium transition-colors ${
            tab === 'existente'
              ? 'border-brand-600 text-brand-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Users size={20} /> Estudiante existente
        </button>
        <button
          type="button"
          onClick={() => setTab('nuevo')}
          className={`flex items-center gap-2 border-b-2 px-3 pb-3 font-medium transition-colors ${
            tab === 'nuevo'
              ? 'border-brand-600 text-brand-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Plus size={20} /> Nuevo estudiante
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {tab === 'existente' && (
        <div className="space-y-4">
          <label className="block text-sm font-medium text-slate-700">
            Buscar estudiante
            <input
              type="search"
              value={busqueda}
              onChange={(event) => setBusqueda(event.target.value)}
              placeholder="Buscar por nombre o CI..."
              className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-2 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
            />
          </label>

          {cargando ? (
            <p className="py-8 text-center text-slate-500">Cargando estudiantes...</p>
          ) : estudiantesFiltrados.length === 0 ? (
            <p className="py-8 text-center text-slate-500">No se encontraron estudiantes.</p>
          ) : (
            <div className="grid max-h-96 gap-3 overflow-y-auto pr-1">
              {estudiantesFiltrados.map((item) => (
                <button
                  type="button"
                  key={item.usuario.id}
                  onClick={() => seleccionarExistente(item)}
                  className={`rounded-lg border p-4 text-left transition-colors ${
                    estudiante?.usuario_id === item.usuario.id && !estudiante.es_nuevo
                      ? 'border-brand-500 bg-brand-50'
                      : 'border-slate-300 hover:border-brand-400 hover:bg-slate-50'
                  }`}
                >
                  <span className="block font-medium text-slate-900">
                    {item.usuario.nombre} {item.usuario.apellido}
                  </span>
                  <span className="block text-sm text-slate-600">
                    CI: {item.usuario.ci} · RUDE: {item.rude || 'Sin RUDE'}
                  </span>
                  <span className="block text-sm text-slate-500">
                    {item.curso?.nombre ? `Curso actual: ${item.curso.nombre}` : 'Sin curso asignado'}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'nuevo' && (
        <div className="space-y-4">
          <p className="rounded-lg border border-brand-200 bg-brand-50 p-3 text-sm text-brand-800">
            Complete los datos personales. La cuenta del estudiante se creará automáticamente.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              CI *
              <input
                value={formNuevo.ci}
                onChange={(event) => actualizarCampo('ci', event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Nombre *
              <input
                value={formNuevo.nombre}
                onChange={(event) => actualizarCampo('nombre', event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Apellido *
              <input
                value={formNuevo.apellido}
                onChange={(event) => actualizarCampo('apellido', event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">
              Correo electrónico *
              <input
                type="email"
                value={formNuevo.email}
                onChange={(event) => actualizarCampo('email', event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Nombre de usuario *
              <input
                value={formNuevo.username}
                onChange={(event) => actualizarCampo('username', event.target.value)}
                autoComplete="username"
                className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Contraseña temporal *
              <input
                type="password"
                value={formNuevo.password}
                onChange={(event) => actualizarCampo('password', event.target.value)}
                autoComplete="new-password"
                className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Sexo
              <select
                value={formNuevo.sexo}
                onChange={(event) => actualizarCampo('sexo', event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-2"
              >
                <option value="M">Masculino</option>
                <option value="F">Femenino</option>
              </select>
            </label>
          </div>
          <button
            type="button"
            onClick={seleccionarNuevo}
            className="w-full rounded-lg bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700"
          >
            Usar como nuevo estudiante
          </button>
          {estudiante?.es_nuevo && (
            <p className="rounded-lg border border-green-200 bg-green-50 p-4 font-medium text-green-800">
              ✓ Nuevo estudiante listo: {estudiante.datos.nombre} {estudiante.datos.apellido}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

import { AlertCircle, CheckCircle2, ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import {
  cambiarInscripcion,
  inscribirEstudiante,
  type InscripcionData,
} from '../api/inscripcion'
import PasoConfirmacion from './inscripcion/components/PasoConfirmacion'
import PasoExitoso from './inscripcion/components/PasoExitoso'
import PasoSeleccionarCurso from './inscripcion/components/PasoSeleccionarCurso'
import PasoSeleccionarOCrearEstudiante from './inscripcion/components/PasoSeleccionarOCrearEstudiante'
import type {
  CursoSeleccionado,
  EstudianteSeleccionado,
  ResultadoInscripcion,
} from './inscripcion/types'

type Paso = 'seleccionar' | 'curso' | 'confirmacion' | 'exitoso' | 'error'

const numeroPaso: Record<Paso, number> = {
  seleccionar: 1,
  curso: 2,
  confirmacion: 3,
  exitoso: 4,
  error: 4,
}

const titulos: Record<Paso, string> = {
  seleccionar: 'Seleccionar o crear estudiante',
  curso: 'Seleccionar curso',
  confirmacion: 'Confirmar inscripción',
  exitoso: 'Inscripción completada',
  error: 'Error en la inscripción',
}

export default function Inscripcion() {
  const [paso, setPaso] = useState<Paso>('seleccionar')
  const [estudiante, setEstudiante] = useState<EstudianteSeleccionado | null>(null)
  const [curso, setCurso] = useState<CursoSeleccionado | null>(null)
  const [rude, setRude] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resultado, setResultado] = useState<ResultadoInscripcion | null>(null)

  const puedeAvanzar =
    (paso === 'seleccionar' && estudiante !== null) ||
    (paso === 'curso' && curso !== null && rude.trim().length > 0) ||
    paso === 'confirmacion'

  const completarInscripcion = async () => {
    if (!estudiante || !curso) return
    setCargando(true)
    setError(null)
    const data: InscripcionData = {
      curso_id: curso.curso_id,
      unidad_id: curso.unidad_id,
      rude: rude.trim(),
      observaciones: observaciones.trim(),
    }

    try {
      let respuesta: ResultadoInscripcion
      if (estudiante.es_nuevo) {
        respuesta = await inscribirEstudiante({ ...data, nuevo_estudiante: estudiante.datos })
      } else {
        if (!estudiante.usuario_id) throw new Error('El estudiante seleccionado no tiene un usuario válido.')
        respuesta = await cambiarInscripcion(estudiante.usuario_id, {
          ...data,
          estudiante_id: estudiante.estudiante_id ?? estudiante.usuario_id,
        })
      }
      setResultado(respuesta)
      setPaso('exitoso')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'No se pudo completar la inscripción.')
      setPaso('error')
    } finally {
      setCargando(false)
    }
  }

  const siguiente = async () => {
    if (paso === 'seleccionar' && estudiante) setPaso('curso')
    else if (paso === 'curso' && curso && rude.trim()) setPaso('confirmacion')
    else if (paso === 'confirmacion') await completarInscripcion()
  }

  const anterior = () => {
    if (paso === 'confirmacion') setPaso('curso')
    else if (paso === 'curso') setPaso('seleccionar')
  }

  const reiniciar = () => {
    setPaso('seleccionar')
    setEstudiante(null)
    setCurso(null)
    setRude('')
    setObservaciones('')
    setError(null)
    setResultado(null)
  }

  return (
    <div className="min-h-[calc(100vh-5rem)] bg-gradient-to-br from-brand-50 to-brand-100 px-4 py-8 text-left">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8 rounded-xl bg-white p-8 shadow-lg">
          <h1 className="mb-2 text-3xl font-bold text-slate-900">Inscripción de estudiantes</h1>
          <p className="text-slate-600">
            Complete el proceso paso a paso para registrar la inscripción de un estudiante.
          </p>
        </header>

        <section aria-label="Progreso de inscripción" className="mb-8 rounded-xl bg-white p-6 shadow-lg">
          <div className="flex items-center">
            {[1, 2, 3, 4].map((numero) => (
              <div key={numero} className={`flex items-center ${numero < 4 ? 'flex-1' : ''}`}>
                <div
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full font-bold transition-colors ${
                    numeroPaso[paso] >= numero
                      ? 'bg-brand-600 text-white'
                      : 'bg-slate-200 text-slate-600'
                  }`}
                >
                  {numeroPaso[paso] > numero ? <CheckCircle2 size={22} /> : numero}
                </div>
                {numero < 4 && (
                  <div
                    className={`mx-2 h-1 flex-1 ${
                      numeroPaso[paso] > numero ? 'bg-brand-600' : 'bg-slate-200'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-4 text-center text-xs text-slate-600 sm:text-sm">
            <span>Estudiante</span>
            <span>Curso</span>
            <span>Confirmación</span>
            <span>Finalizar</span>
          </div>
        </section>

        <section className="rounded-xl bg-white p-5 shadow-lg sm:p-8">
          <h2 className="mb-6 text-2xl font-bold text-slate-900">{titulos[paso]}</h2>
          <div className="mb-8 min-h-96">
            {paso === 'seleccionar' && (
              <PasoSeleccionarOCrearEstudiante estudiante={estudiante} onSelect={setEstudiante} />
            )}
            {paso === 'curso' && (
              <PasoSeleccionarCurso
                curso={curso}
                rude={rude}
                onSelect={setCurso}
                onRudeChange={setRude}
              />
            )}
            {paso === 'confirmacion' && (
              <PasoConfirmacion
                estudiante={estudiante}
                curso={curso}
                rude={rude}
                observaciones={observaciones}
                onObservacionesChange={setObservaciones}
              />
            )}
            {paso === 'exitoso' && resultado && <PasoExitoso resultado={resultado} />}
            {paso === 'error' && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-800">
                <div className="mb-4 flex items-center gap-3">
                  <AlertCircle size={28} />
                  <h3 className="text-lg font-semibold">Error en la inscripción</h3>
                </div>
                <p>{error}</p>
                <p className="mt-2 text-sm">Verifique los datos e intente nuevamente.</p>
              </div>
            )}
          </div>

          {paso === 'exitoso' || paso === 'error' ? (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={reiniciar}
                className="rounded-lg bg-brand-600 px-6 py-3 font-medium text-white hover:bg-brand-700"
              >
                Nueva inscripción
              </button>
            </div>
          ) : (
            <div className="flex justify-between gap-4">
              <button
                type="button"
                onClick={anterior}
                disabled={paso === 'seleccionar'}
                className="flex items-center gap-2 rounded-lg bg-slate-200 px-5 py-3 font-medium text-slate-700 hover:bg-slate-300 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <ChevronLeft size={20} /> Anterior
              </button>
              <button
                type="button"
                onClick={siguiente}
                disabled={!puedeAvanzar || cargando}
                className="flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-3 font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {cargando ? 'Procesando...' : paso === 'confirmacion' ? 'Completar inscripción' : 'Siguiente'}
                <ChevronRight size={20} />
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

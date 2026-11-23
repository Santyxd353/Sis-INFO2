import { AlertCircle } from 'lucide-react'
import type { CursoSeleccionado, EstudianteSeleccionado } from '../types'

interface Props {
  estudiante: EstudianteSeleccionado | null
  curso: CursoSeleccionado | null
  rude: string
  observaciones: string
  onObservacionesChange: (observaciones: string) => void
}

export default function PasoConfirmacion({
  estudiante,
  curso,
  rude,
  observaciones,
  onObservacionesChange,
}: Props) {
  if (!estudiante || !curso) return <p className="text-slate-500">Datos incompletos.</p>

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-brand-200 bg-brand-50 p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">Información del estudiante</h3>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-slate-600">Nombre</dt>
            <dd className="font-medium text-slate-900">
              {estudiante.datos.nombre} {estudiante.datos.apellido}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-slate-600">CI</dt>
            <dd className="font-medium text-slate-900">{estudiante.datos.ci}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-600">Correo electrónico</dt>
            <dd className="font-medium text-slate-900">{estudiante.datos.email}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-600">Sexo</dt>
            <dd className="font-medium text-slate-900">
              {estudiante.datos.sexo === 'M' ? 'Masculino' : 'Femenino'}
            </dd>
          </div>
        </dl>
        {estudiante.es_nuevo && (
          <p className="mt-4 rounded border border-green-300 bg-green-100 p-3 text-sm text-green-800">
            ✓ Se creará la ficha de este estudiante al completar la inscripción.
          </p>
        )}
      </section>

      <section className="rounded-lg border border-brand-200 bg-brand-50 p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">Información de inscripción</h3>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-slate-600">Unidad educativa</dt>
            <dd className="font-medium text-slate-900">{curso.unidad_nombre}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-600">Grado</dt>
            <dd className="font-medium text-slate-900">{curso.grado}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-600">Paralelo</dt>
            <dd className="font-medium text-slate-900">{curso.paralelo}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-600">Curso</dt>
            <dd className="font-medium text-slate-900">{curso.curso_nombre}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-sm text-slate-600">RUDE</dt>
            <dd className="font-medium text-slate-900">{rude}</dd>
          </div>
        </dl>
      </section>

      <label className="block text-sm font-medium text-slate-700">
        Observaciones (opcional)
        <textarea
          value={observaciones}
          onChange={(event) => onObservacionesChange(event.target.value)}
          placeholder="Agregue cualquier nota o comentario sobre esta inscripción..."
          rows={4}
          className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-2"
        />
      </label>

      <div className="flex gap-3 rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-900">
        <AlertCircle className="shrink-0 text-yellow-600" size={20} />
        <div>
          <p className="font-medium">Revise los datos antes de continuar</p>
          <p>
            Al completar la inscripción, el movimiento quedará registrado en el historial del
            estudiante.
          </p>
        </div>
      </div>
    </div>
  )
}

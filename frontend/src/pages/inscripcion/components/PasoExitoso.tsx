import { CheckCircle2, Download } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ResultadoInscripcion } from '../types'

interface Props {
  resultado: ResultadoInscripcion
}

export default function PasoExitoso({ resultado }: Props) {
  const descargarComprobante = () => {
    const contenido = `COMPROBANTE DE INSCRIPCIÓN
============================

Estudiante: ${resultado.usuario.nombre} ${resultado.usuario.apellido}
CI: ${resultado.usuario.ci}
Email: ${resultado.usuario.email}

Información de inscripción:
- Curso: ${resultado.curso?.nombre ?? 'N/A'}
- Unidad: ${resultado.unidad?.nombre ?? 'N/A'}
- RUDE: ${resultado.rude}
- Estado: ${resultado.estado ? 'Activo' : 'Inactivo'}

Fecha de inscripción: ${new Date().toLocaleDateString('es-BO')}
`
    const archivo = new Blob([contenido], { type: 'text/plain;charset=utf-8' })
    const enlace = document.createElement('a')
    enlace.href = URL.createObjectURL(archivo)
    enlace.download = `comprobante_inscripcion_${resultado.usuario.ci}.txt`
    enlace.click()
    URL.revokeObjectURL(enlace.href)
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border-2 border-green-400 bg-green-50 p-8 text-center">
        <CheckCircle2 className="mx-auto mb-4 text-green-600" size={64} />
        <h2 className="mb-2 text-3xl font-bold text-green-800">¡Inscripción completada!</h2>
        <p className="text-lg text-green-700">
          El estudiante fue inscrito correctamente en el sistema.
        </p>
      </div>

      <section className="space-y-4 rounded-lg bg-slate-50 p-6">
        <h3 className="text-lg font-semibold text-slate-900">Datos de la inscripción</h3>
        <dl className="grid gap-4 sm:grid-cols-2">
          <Detalle titulo="Estudiante">
            {resultado.usuario.nombre} {resultado.usuario.apellido}
          </Detalle>
          <Detalle titulo="CI">{resultado.usuario.ci}</Detalle>
          <Detalle titulo="RUDE">{resultado.rude}</Detalle>
          <Detalle titulo="Curso">{resultado.curso?.nombre ?? 'N/A'}</Detalle>
          <Detalle titulo="Unidad educativa">{resultado.unidad?.nombre ?? 'N/A'}</Detalle>
          <Detalle titulo="Estado">{resultado.estado ? '✓ Activo' : 'Inactivo'}</Detalle>
        </dl>
      </section>

      <button
        type="button"
        onClick={descargarComprobante}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-6 py-3 font-medium text-white hover:bg-brand-700"
      >
        <Download size={20} /> Descargar comprobante
      </button>

      <section className="rounded-lg border border-brand-200 bg-brand-50 p-6">
        <h3 className="mb-3 text-lg font-semibold text-slate-900">Próximos pasos</h3>
        <ol className="list-inside list-decimal space-y-2 text-slate-700">
          <li>Asignar tutores o apoderados al estudiante.</li>
          <li>Configurar materias y docentes para el curso.</li>
          <li>Completar la información adicional del estudiante.</li>
        </ol>
      </section>
    </div>
  )
}

function Detalle({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-4">
      <dt className="text-sm text-slate-600">{titulo}</dt>
      <dd className="font-medium text-slate-900">{children}</dd>
    </div>
  )
}

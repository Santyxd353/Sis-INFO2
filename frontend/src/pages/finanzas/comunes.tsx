import { Search, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { buscarEstudiantes, type EstudianteElegible } from '../../api/finanzas'
import { errorTexto } from './utilidades'

export function BuscadorEstudiante({ unidadId, seleccionado, onSeleccionar }: {
  unidadId: number
  seleccionado: EstudianteElegible | null
  onSeleccionar: (estudiante: EstudianteElegible | null) => void
}) {
  const [busqueda, setBusqueda] = useState('')
  const [candidatos, setCandidatos] = useState<EstudianteElegible[]>([])
  const [mensaje, setMensaje] = useState('')
  const buscar = async () => {
    setMensaje('')
    try {
      const { data } = await buscarEstudiantes({ unidad_educativa: unidadId, buscar: busqueda.trim() })
      setCandidatos(data)
      if (data.length === 0) setMensaje('No se encontraron estudiantes.')
    } catch (e) { setMensaje(errorTexto(e, 'No fue posible buscar estudiantes.')) }
  }
  if (seleccionado) return (
    <div className="flex items-center justify-between rounded-lg border p-2">
      <span>{seleccionado.nombre} · {seleccionado.curso_nombre ?? 'Sin curso'}</span>
      <button className="text-sm underline" onClick={() => onSeleccionar(null)}>Cambiar</button>
    </div>
  )
  return <div className="space-y-2">
    <div className="flex gap-2">
      <input aria-label="Buscar estudiante" placeholder="Nombre, apellido o RUDE" value={busqueda} onChange={e => setBusqueda(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') void buscar() }} className="w-full rounded-lg border p-2" />
      <button className="btn-secondary" aria-label="Buscar" onClick={() => void buscar()}><Search size={17} /></button>
    </div>
    {mensaje && <p className="text-sm text-slate-500">{mensaje}</p>}
    {candidatos.length > 0 && <ul className="max-h-48 overflow-y-auto rounded-lg border bg-white">
      {candidatos.map(c => <li key={c.id}><button className="w-full p-2 text-left hover:bg-brand-50" onClick={() => { onSeleccionar(c); setCandidatos([]) }}>
        {c.nombre} <span className="text-xs text-slate-500">{c.curso_nombre ?? 'Sin curso'} · RUDE {c.rude}</span>
      </button></li>)}
    </ul>}
  </div>
}

export function Tarjeta({ titulo, valor, detalle, tono = 'slate' }: { titulo: string; valor: ReactNode; detalle?: ReactNode; tono?: 'slate' | 'red' | 'emerald' | 'amber' }) {
  const tonos = { slate: 'text-slate-900', red: 'text-red-700', emerald: 'text-emerald-700', amber: 'text-amber-700' }
  return <div className="rounded-2xl bg-white p-4 shadow-sm">
    <p className="text-sm text-slate-500">{titulo}</p>
    <p className={`mt-1 text-2xl font-bold ${tonos[tono]}`}>{valor}</p>
    {detalle && <p className="mt-1 text-xs text-slate-500">{detalle}</p>}
  </div>
}

export function Modal({ title, close, children, ancho = 'max-w-md' }: { title: string; close: () => void; children: ReactNode; ancho?: string }) {
  return (
    <div role="dialog" aria-modal="true" aria-label={title} className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4">
      <div className={`max-h-[90vh] w-full overflow-y-auto rounded-2xl bg-white p-6 ${ancho}`}>
        <button aria-label="Cerrar formulario" className="float-right" onClick={close}><X size={20} /></button>
        <h2 className="text-xl font-bold">{title}</h2>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  )
}

export function Campo({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block text-sm font-medium">{label}<div className="mt-1">{children}</div></label>
}

export function Avisos({ error, exito, reintentar }: { error: string; exito: string; reintentar?: () => void }) {
  return <>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-700">{error} {reintentar && <button className="underline" onClick={reintentar}>Reintentar</button>}</p>}
    {exito && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-emerald-700">{exito}</p>}
  </>
}

const ESTILOS_ESTADO: Record<string, string> = {
  BORRADOR: 'bg-slate-100 text-slate-700', ACTIVO: 'bg-emerald-50 text-emerald-700', VIGENTE: 'bg-emerald-50 text-emerald-700',
  INACTIVO: 'bg-slate-100 text-slate-500', REVOCADA: 'bg-slate-100 text-slate-500', ANULADA: 'bg-slate-100 text-slate-500',
  VALIDO: 'bg-emerald-50 text-emerald-700', ANULADO: 'bg-slate-100 text-slate-500',
  PENDIENTE: 'bg-amber-50 text-amber-700', PAGADA: 'bg-emerald-50 text-emerald-700', VENCIDA: 'bg-red-50 text-red-700',
  CONCILIADA: 'bg-emerald-50 text-emerald-700', EXPIRADA: 'bg-slate-100 text-slate-500',
  OBSERVADA: 'bg-red-50 text-red-700', DESCUADRE: 'bg-red-50 text-red-700',
}

export function Estado({ valor }: { valor: string }) {
  return <span className={`rounded-full px-2 py-1 text-xs font-semibold ${ESTILOS_ESTADO[valor] ?? 'bg-slate-100'}`}>{valor.charAt(0) + valor.slice(1).toLowerCase()}</span>
}

export function Tabla({ columnas, vacio, cargando, children }: { columnas: string[]; vacio: boolean; cargando: boolean; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50"><tr>{columnas.map(c => <th key={c} className="p-4">{c}</th>)}</tr></thead>
        <tbody>
          {cargando ? <tr><td className="p-6" colSpan={columnas.length}>Cargando...</td></tr>
            : vacio ? <tr><td className="p-6" colSpan={columnas.length}>No hay registros.</td></tr>
              : children}
        </tbody>
      </table>
    </div>
  )
}

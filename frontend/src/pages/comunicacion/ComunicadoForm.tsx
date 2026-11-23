import { useState } from 'react'
import type { Comunicado } from '../../api/comunicacion'
import { actualizarComunicado, crearComunicado } from '../../api/comunicacion'
import { useAuth } from '../../app/contexts/AuthContext'
import { Errors, Field } from '../workflows/WorkflowUI'
import { useOperation } from '../workflows/useWorkflow'
import { useCatalogo } from './useComunicacion'

export function UnidadComunicacion({ value, onChange, disabled = false }: { value: string; onChange: (value: string) => void; disabled?: boolean }) {
  const { user } = useAuth()
  const fixed = user?.alcance?.tipo === 'UNIDAD'
  const units = useCatalogo<{ id: number; nombre: string }>('/institucion/unidades-educativas/', { colegio: user?.alcance?.colegio_id ?? '' }, !fixed && Boolean(user?.alcance?.colegio_id))
  return <div className="space-y-2"><Field label="Unidad educativa *"><select className="wf-input" required value={value} disabled={disabled || fixed || units.loading || Boolean(units.error)} onChange={e => onChange(e.target.value)}>
    <option value="">Seleccione una unidad</option>
    {fixed ? <option value={user?.alcance?.unidad_id ?? ''}>{user?.alcance?.unidad_nombre ?? user?.unidad?.nombre ?? 'Unidad asignada'}</option> : units.items.map(unit => <option key={unit.id} value={unit.id}>{unit.nombre}</option>)}
  </select></Field>{units.loading && <p role="status">Cargando unidades...</p>}{units.error && <p role="alert">{units.error} <button type="button" className="wf-secondary" onClick={units.retry}>Reintentar unidades</button></p>}</div>
}

export default function ComunicadoForm({ initial, onCancel, onDone }: { initial?: Comunicado; onCancel: () => void; onDone: () => void }) {
  const { user } = useAuth()
  const [unidad, setUnidad] = useState(String(initial?.unidad_educativa ?? user?.alcance?.unidad_id ?? ''))
  const [curso, setCurso] = useState(String(initial?.curso ?? ''))
  const [titulo, setTitulo] = useState(initial?.titulo ?? '')
  const [cuerpo, setCuerpo] = useState(initial?.cuerpo ?? '')
  const [prioridad, setPrioridad] = useState<Comunicado['prioridad']>(initial?.prioridad ?? 'NORMAL')
  const [confirmacion, setConfirmacion] = useState(initial?.requiere_confirmacion ?? true)
  const courses = useCatalogo<{ id: number; nombre: string }>('/academico/cursos/', { unidad_educativa: unidad }, Boolean(unidad))
  const op = useOperation()
  const locked = op.busy || op.denied
  return <form aria-label="Formulario de comunicado" className="wf-card wf-form" onSubmit={e => {
    e.preventDefault()
    if (!unidad || !titulo.trim() || !cuerpo.trim()) return
    const payload = { titulo: titulo.trim(), cuerpo: cuerpo.trim(), unidad_educativa: Number(unidad), curso: curso ? Number(curso) : null, prioridad, requiere_confirmacion: confirmacion }
    void op.run(() => initial ? actualizarComunicado(initial.id, payload) : crearComunicado(payload), onDone)
  }}>
    <h2>{initial ? 'Editar borrador' : 'Nuevo comunicado'}</h2>
    <p className="text-sm text-slate-600">Guarde el borrador y revise su contenido antes de publicarlo.</p>
    <Errors errors={op.errors} />
    <fieldset disabled={locked} className="grid gap-4 md:grid-cols-2">
      <UnidadComunicacion value={unidad} onChange={value => { setUnidad(value); setCurso('') }} />
      <div className="space-y-2"><Field label="Curso destinatario"><select className="wf-input" value={curso} disabled={!unidad || courses.loading || Boolean(courses.error)} onChange={e => setCurso(e.target.value)}><option value="">Toda la unidad educativa</option>{courses.items.map(course => <option key={course.id} value={course.id}>{course.nombre}</option>)}</select></Field>{courses.loading && <p role="status">Cargando cursos...</p>}{courses.error && <p role="alert">{courses.error} <button type="button" className="wf-secondary" onClick={courses.retry}>Reintentar cursos</button></p>}</div>
      <Field label="Título *"><input className="wf-input" required maxLength={200} value={titulo} onChange={e => setTitulo(e.target.value)} /></Field>
      <Field label="Prioridad"><select className="wf-input" value={prioridad} onChange={e => setPrioridad(e.target.value as Comunicado['prioridad'])}><option value="NORMAL">Normal</option><option value="URGENTE">Urgente</option></select></Field>
      <div className="md:col-span-2"><Field label="Contenido *"><textarea className="wf-input" required maxLength={20000} rows={6} value={cuerpo} onChange={e => setCuerpo(e.target.value)} /></Field></div>
      <label className="flex items-center gap-2"><input type="checkbox" checked={confirmacion} onChange={e => setConfirmacion(e.target.checked)} />Solicitar confirmación de lectura</label>
    </fieldset>
    <div className="flex flex-wrap gap-3"><button className="wf-primary" disabled={locked || !unidad || !titulo.trim() || !cuerpo.trim() || courses.loading || Boolean(courses.error)}>{op.busy ? 'Guardando...' : 'Guardar borrador'}</button><button type="button" className="wf-secondary" disabled={op.busy} onClick={onCancel}>Cancelar</button></div>
  </form>
}

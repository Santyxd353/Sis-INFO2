import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../app/contexts/AuthContext'
import { guardarHorario, type AsignacionHorario, type AulaHorario, type Horario } from '../../api/horarios'
import { useOperation } from '../workflows/useWorkflow'
import { Errors, Field } from '../workflows/WorkflowUI'
import CatalogoHorario from './CatalogoHorario'

const dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
export default function HorarioForm({ initial, onDone, onCancel, onDenied }: { initial?: Horario; onDone: () => void; onCancel: () => void; onDenied: () => void }) {
  const { can, user } = useAuth()
  const [assignment, setAssignment] = useState<AsignacionHorario | null>(() => initial ? { id: initial.asignacion_docente, nombre: `${initial.profesor_nombre} · ${initial.materia_nombre} · ${initial.curso_nombre} · ${initial.gestion}`, profesor: initial.profesor, curso: initial.curso, unidad_educativa: initial.unidad_educativa, colegio: initial.colegio, gestion: initial.gestion, fecha_inicio: initial.fecha_inicio, fecha_fin: initial.fecha_fin ?? '' } : null)
  const [room, setRoom] = useState<AulaHorario | null>(() => initial ? { id: initial.aula, nombre: initial.aula_nombre, colegio: initial.colegio, unidad_educativa: initial.unidad_educativa } : null)
  const [form, setForm] = useState({ dia: initial?.dia ?? 1, hora_inicio: initial?.hora_inicio ?? '', hora_fin: initial?.hora_fin ?? '', fecha_inicio: initial?.fecha_inicio ?? '', fecha_fin: initial?.fecha_fin ?? '' })
  const [validation, setValidation] = useState<Record<string, string>>({})
  const op = useOperation()
  const errors = { ...op.errors, ...validation }
  function save() {
    const issues: Record<string, string> = {}
    if (!assignment) issues.asignacion_docente = 'Seleccione una asignación docente.'
    if (!room) issues.aula = 'Seleccione un aula del colegio de la asignación.'
    if (!form.hora_inicio || !form.hora_fin) issues.hora_inicio = 'Complete ambas horas.'
    else if (`${form.hora_fin}:00`.slice(0, 8) <= `${form.hora_inicio}:00`.slice(0, 8)) issues.hora_fin = 'La hora de fin debe ser posterior al inicio.'
    if (!form.fecha_inicio || !form.fecha_fin) issues.fecha_inicio = 'Complete ambas fechas de vigencia.'
    else if (form.fecha_fin < form.fecha_inicio) issues.fecha_fin = 'La fecha final debe ser igual o posterior al inicio.'
    setValidation(issues)
    if (Object.keys(issues).length || !assignment || !room) return
    void op.run(() => guardarHorario({ ...form, asignacion_docente: assignment.id, aula: room.id }, initial?.id), onDone, status => { if (status === 403) onDenied() })
  }
  return <form aria-label="Formulario de horario" className="wf-card wf-form" onSubmit={e => { e.preventDefault(); save() }}>
    <h2>{initial ? 'Editar horario' : 'Nuevo horario'}</h2>
    <Errors errors={op.errors} />
    <p className="text-sm text-slate-600">Seleccione una asignación vigente. El aula debe pertenecer a la misma unidad educativa. Los campos con * son obligatorios.</p>
    <fieldset disabled={op.busy || op.denied} className="grid gap-4 md:grid-cols-2">
      <CatalogoHorario label="Asignación docente *" endpoint="/academico/horarios-asignaciones/" value={assignment} required error={errors.asignacion_docente} onChange={value => { setAssignment(value); setRoom(null); if (value) setForm(current => ({ ...current, fecha_inicio: value.fecha_inicio, fecha_fin: value.fecha_fin })) }} />
      <div className="space-y-2"><CatalogoHorario key={assignment?.id ?? 'none'} label="Aula *" endpoint="/academico/horarios-aulas/" params={{ asignacion_docente: assignment?.id ?? '' }} value={room} required disabled={!assignment} error={errors.aula} onChange={setRoom} emptyMessage={<>{'No existen aulas activas configuradas para la unidad educativa de esta asignación. '} {(can('modulo', 'crear') || can('aula', 'crear')) && user?.alcance?.tipo !== 'PERSONAL' && <Link className="text-brand-700 underline" to="/dashboard/infraestructura">Configurar infraestructura</Link>}</>} />{!assignment && <p className="text-sm text-slate-600">Seleccione primero la asignación docente.</p>}</div>
      <Field label="Día *"><select className="wf-input" value={form.dia} onChange={e => setForm({ ...form, dia: Number(e.target.value) })}>{dias.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}</select></Field>
      <div />
      <Field label="Hora de inicio *" error={errors.hora_inicio}><input className="wf-input" type="time" step="1" required value={form.hora_inicio} onChange={e => setForm({ ...form, hora_inicio: e.target.value })} /></Field>
      <Field label="Hora de fin *" error={errors.hora_fin}><input className="wf-input" type="time" step="1" required value={form.hora_fin} onChange={e => setForm({ ...form, hora_fin: e.target.value })} /></Field>
      <Field label="Vigente desde *" error={errors.fecha_inicio}><input className="wf-input" type="date" required value={form.fecha_inicio} onChange={e => setForm({ ...form, fecha_inicio: e.target.value })} /></Field>
      <Field label="Vigente hasta *" error={errors.fecha_fin}><input className="wf-input" type="date" required value={form.fecha_fin} onChange={e => setForm({ ...form, fecha_fin: e.target.value })} /></Field>
    </fieldset>
    <div className="flex flex-wrap gap-3"><button className="wf-primary" disabled={op.busy || op.denied}>{op.busy ? 'Guardando...' : 'Guardar horario'}</button><button type="button" className="wf-secondary" disabled={op.busy} onClick={onCancel}>Cancelar</button></div>
  </form>
}

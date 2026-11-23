import { useState } from 'react'
import { emitirAlerta, type AlertaPayload } from '../../api/comunicacion'
import { useAuth } from '../../app/contexts/AuthContext'
import { Errors, Field } from '../workflows/WorkflowUI'
import { useOperation } from '../workflows/useWorkflow'
import { UnidadComunicacion } from './ComunicadoForm'
import { useCatalogo } from './useComunicacion'

interface EstudianteAlerta { id: number; unidad: number | { id: number }; usuario: { nombre: string; apellido: string } }
export default function AlertaForm({ onDone, onCancel }: { onDone: (created: number) => void; onCancel: () => void }) {
  const { user } = useAuth()
  const [unidad, setUnidad] = useState(String(user?.alcance?.unidad_id ?? ''))
  const [estudiante, setEstudiante] = useState('')
  const [tipo, setTipo] = useState<AlertaPayload['tipo']>('PAGO')
  const [titulo, setTitulo] = useState(''), [cuerpo, setCuerpo] = useState('')
  const [clave, setClave] = useState<string>(() => crypto.randomUUID())
  const students = useCatalogo<EstudianteAlerta>('/estudiantes/estudiantes/', {}, Boolean(unidad))
  const options = students.items.filter(item => Number(typeof item.unidad === 'object' ? item.unidad.id : item.unidad) === Number(unidad))
  const op = useOperation()
  return <form aria-label="Alerta administrativa" className="wf-card wf-form" onSubmit={e => {
    e.preventDefault()
    if (!options.some(item => item.id === Number(estudiante)) || !titulo.trim() || !cuerpo.trim() || !clave.trim()) return
    void op.run(async () => { const { data } = await emitirAlerta({ estudiante: Number(estudiante), tipo, titulo: titulo.trim(), cuerpo: cuerpo.trim(), clave_evento: clave.trim() }); onDone(data.creadas) }, () => {})
  }}><h2>Emitir alerta administrativa</h2><p className="text-sm text-slate-600">Aviso al estudiante y a sus tutores. Para pagos, registre únicamente un aviso; los cobros se gestionan con administración.</p><Errors errors={op.errors} /><fieldset disabled={op.busy || op.denied} className="grid gap-4 md:grid-cols-2"><UnidadComunicacion value={unidad} onChange={value => { setUnidad(value); setEstudiante('') }} /><div className="space-y-2"><Field label="Estudiante *"><select className="wf-input" required value={estudiante} disabled={!unidad || students.loading || Boolean(students.error)} onChange={e => setEstudiante(e.target.value)}><option value="">Seleccione un estudiante</option>{options.map(item => <option key={item.id} value={item.id}>{item.usuario.nombre} {item.usuario.apellido}</option>)}</select></Field>{students.loading && <p role="status">Cargando estudiantes...</p>}{students.error && <p role="alert">{students.error} <button className="wf-secondary" type="button" onClick={students.retry}>Reintentar estudiantes</button></p>}{unidad && !students.loading && !students.error && !options.length && <p>No hay estudiantes en esta unidad.</p>}</div><Field label="Tipo de alerta"><select className="wf-input" value={tipo} onChange={e => setTipo(e.target.value as AlertaPayload['tipo'])}><option value="PAGO">Pago</option><option value="CONTINGENCIA">Contingencia</option></select></Field><Field label="Referencia del evento *"><input className="wf-input" required maxLength={120} value={clave} onChange={e => setClave(e.target.value)} /><span className="text-xs text-slate-600">Conserve esta referencia al reintentar el mismo evento para evitar avisos duplicados.</span></Field><Field label="Título de alerta *"><input className="wf-input" required maxLength={200} value={titulo} onChange={e => setTitulo(e.target.value)} /></Field><Field label="Mensaje de alerta *"><textarea className="wf-input" required maxLength={20000} rows={4} value={cuerpo} onChange={e => setCuerpo(e.target.value)} /></Field></fieldset><div className="flex flex-wrap gap-3"><button className="wf-primary" disabled={op.busy || op.denied || !estudiante || !titulo.trim() || !cuerpo.trim() || !clave.trim() || students.loading || Boolean(students.error)}>{op.busy ? 'Enviando...' : 'Enviar alerta'}</button><button type="button" className="wf-secondary" disabled={op.busy} onClick={onCancel}>Cancelar</button></div></form>
}

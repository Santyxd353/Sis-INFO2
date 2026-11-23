import { useState } from 'react'
import { CATEGORIAS, guardarPreferencias, type Categoria, type Preferencias } from '../../api/comunicacion'
import { Errors } from '../workflows/WorkflowUI'
import { useOperation } from '../workflows/useWorkflow'

export default function PreferenciasForm({ initial }: { initial: Preferencias }) {
  const [values, setValues] = useState(initial), [success, setSuccess] = useState('')
  const op = useOperation()
  return <form className="wf-card wf-form" aria-label="Preferencias de notificaciones" onSubmit={e => { e.preventDefault(); setSuccess(''); void op.run(() => guardarPreferencias(values), () => setSuccess('Preferencias guardadas.')) }}><h2>Preferencias de avisos</h2><p className="text-sm text-slate-600">Elija qué categorías pueden enviar avisos push al dispositivo. Los avisos permanecen en la bandeja aunque desactive el push.</p><Errors errors={op.errors} />{success && <p role="status" className="wf-success">{success}</p>}<fieldset disabled={op.busy || op.denied} className="grid gap-3 sm:grid-cols-2">{(Object.keys(CATEGORIAS) as Categoria[]).map(category => <label key={category} className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={values[category] ?? true} onChange={e => { setValues({ ...values, [category]: e.target.checked }); setSuccess('') }} />{CATEGORIAS[category]}</label>)}</fieldset><button className="wf-primary justify-self-start" disabled={op.busy || op.denied}>{op.busy ? 'Guardando...' : 'Guardar preferencias'}</button></form>
}

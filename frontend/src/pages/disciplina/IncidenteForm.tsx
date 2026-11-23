import { useState } from 'react'
import { guardarIncidente, type Incidente } from '../../api/schoolWorkflows'
import { useOperation } from '../workflows/useWorkflow'
import { Errors, Field } from '../workflows/WorkflowUI'

function localTime(value:string) { const date=new Date(value); return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16) }
export default function IncidenteForm({enrollment,initial,onDone,onCancel}:{enrollment:number;initial?:Incidente;onDone:()=>void;onCancel:()=>void}) {
  const [form,setForm]=useState({fecha:localTime(initial?.fecha??new Date().toISOString()),tipo:initial?.tipo??'OBSERVACION',severidad:initial?.severidad??'LEVE',descripcion:initial?.descripcion??'',estado:initial?.estado??'ABIERTO'})
  const op=useOperation()
  return <form className="wf-card wf-form" onSubmit={e=>{e.preventDefault();void op.run(()=>guardarIncidente({...form,historial_inscripcion:enrollment,fecha:new Date(form.fecha).toISOString()},initial?.id),onDone)}}>
    <h2>{initial?'Editar observación':'Nueva observación'}</h2><Errors errors={op.errors}/>
    <fieldset disabled={op.busy||op.denied} className="grid gap-4 sm:grid-cols-2">
      <Field label="Fecha *" error={op.errors.fecha}><input className="wf-input" type="datetime-local" required value={form.fecha} onChange={e=>setForm({...form,fecha:e.target.value})}/></Field>
      <Field label="Tipo *" error={op.errors.tipo}><select className="wf-input" value={form.tipo} onChange={e=>setForm({...form,tipo:e.target.value})}><option value="OBSERVACION">Observación</option><option value="FALTA">Falta disciplinaria</option></select></Field>
      <Field label="Gravedad *" error={op.errors.severidad}><select className="wf-input" value={form.severidad} onChange={e=>setForm({...form,severidad:e.target.value})}>{['LEVE','MODERADA','GRAVE'].map(v=><option key={v}>{v}</option>)}</select></Field>
      <Field label="Estado"><select className="wf-input" value={form.estado} onChange={e=>setForm({...form,estado:e.target.value})}><option>ABIERTO</option><option>CERRADO</option></select></Field>
      <div className="sm:col-span-2"><Field label="Descripción *" error={op.errors.descripcion}><textarea className="wf-input" required rows={3} value={form.descripcion} onChange={e=>setForm({...form,descripcion:e.target.value})}/></Field></div>
    </fieldset>
    <div className="flex flex-wrap gap-3"><button className="wf-primary" disabled={op.busy||op.denied}>{op.busy?'Guardando...':'Guardar observación'}</button><button type="button" className="wf-secondary" disabled={op.busy} onClick={onCancel}>Cancelar</button></div>
  </form>
}

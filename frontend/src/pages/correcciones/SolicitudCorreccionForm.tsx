import { useState } from 'react'
import { solicitarCorreccion,type CalificacionCorregible } from '../../api/schoolWorkflows'
import { useOperation,usePaged } from '../workflows/useWorkflow'
import { Errors,Field,Pages,Status } from '../workflows/WorkflowUI'

export default function SolicitudCorreccionForm({onDone,onCancel}:{onDone:()=>void;onCancel:()=>void}) {
  const [page,setPage]=useState(1),[form,setForm]=useState({calificacion:'',valor_nuevo:'',motivo:''})
  const [selected,setSelected]=useState<CalificacionCorregible|null>(null)
  const data=usePaged<CalificacionCorregible>('/academico/calificaciones-corregibles/',{page})
  const op=useOperation()
  return <form className="wf-card wf-form" onSubmit={e=>{e.preventDefault();void op.run(()=>solicitarCorreccion({calificacion:Number(form.calificacion),valor_nuevo:form.valor_nuevo,motivo:form.motivo}),onDone)}}>
    <h2>Nueva solicitud de corrección</h2><p className="text-sm text-slate-600">Solo notas de sus actividades en periodos finalizados. La nota no cambia hasta recibir autorización.</p><Errors errors={op.errors}/>
    <Status loading={data.loading} error={data.error} empty={!data.items.length}/>
    <fieldset className="wf-form" disabled={op.busy||op.denied}>
      <Field label="Calificación *" error={op.errors.calificacion}><select className="wf-input" required value={form.calificacion} onChange={e=>{setForm({...form,calificacion:e.target.value});setSelected(data.items.find(g=>g.id===Number(e.target.value))??null)}}><option value="">Seleccione estudiante y actividad</option>{selected&&!data.items.some(g=>g.id===selected.id)&&<option value={selected.id}>{selected.estudiante_nombre} · {selected.actividad_nombre}</option>}{data.items.map(g=><option key={g.id} value={g.id}>{g.estudiante_nombre} · {g.curso_nombre} · {g.materia_nombre} · {g.actividad_nombre} · {g.periodo_nombre}</option>)}</select></Field>
      {selected&&<p className="rounded-lg bg-slate-50 p-3">Nota actual: <strong>{selected.valor}</strong> / {selected.puntaje_maximo}</p>}
      <Field label="Valor propuesto *" error={op.errors.valor_nuevo}><input className="wf-input" required type="number" min="0" max={selected?.puntaje_maximo} step="0.01" value={form.valor_nuevo} onChange={e=>setForm({...form,valor_nuevo:e.target.value})}/></Field>
      <Field label="Motivo *" error={op.errors.motivo}><textarea className="wf-input" rows={3} required value={form.motivo} onChange={e=>setForm({...form,motivo:e.target.value})}/></Field>
    </fieldset>
    {data.count>20&&<Pages page={page} count={data.count} onChange={setPage}/>}
    <div className="flex flex-wrap gap-3"><button className="wf-primary" disabled={op.busy||op.denied||!selected}>{op.busy?'Enviando...':'Enviar solicitud'}</button><button type="button" className="wf-secondary" disabled={op.busy} onClick={onCancel}>Cancelar</button></div>
  </form>
}

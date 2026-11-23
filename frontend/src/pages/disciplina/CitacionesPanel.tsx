import { useState } from 'react'
import { guardarCitacion,cambiarEstadoCitacion,type Citacion,type Incidente,type TutorDisciplina } from '../../api/schoolWorkflows'
import { useOperation,usePaged } from '../workflows/useWorkflow'
import { Errors,Field,Pages,Status } from '../workflows/WorkflowUI'
import { useAuth } from '../../app/contexts/AuthContext'

export default function CitacionesPanel({incident,onClose,onSuccess}:{incident:Incidente;onClose:()=>void;onSuccess:(text:string)=>void}) {
  const {can}=useAuth()
  const [version,setVersion]=useState(0),[page,setPage]=useState(1),[form,setForm]=useState<Citacion|true|null>(null)
  const data=usePaged<Citacion>('/estudiantes/citaciones/',{incidente:incident.id,page},version)
  const op=useOperation()
  const saved=()=>{setForm(null);setVersion(v=>v+1);onSuccess('Citación guardada.')}
  return <section className="wf-card space-y-4" aria-label="Citaciones">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2>Citaciones · incidente {incident.id}</h2><button className="wf-secondary" onClick={onClose}>Cerrar citaciones</button></div>
    <p className="text-sm text-slate-600">{incident.descripcion}</p><Errors errors={op.errors}/>
    {can('disciplina','crear')&&!form&&<button className="wf-primary" onClick={()=>setForm(true)}>Nueva citación</button>}
    {form&&<CitationForm key={form===true?'new':form.id} incident={incident} initial={form===true?undefined:form} onDone={saved} onCancel={()=>setForm(null)}/>}
    <Status loading={data.loading} error={data.error} empty={!data.items.length}/>
    {data.items.map(row=><article className="rounded-xl border border-slate-200 p-4 space-y-2" key={row.id}>
      <p className="font-semibold">{row.tutor_nombre} · {row.estado}</p><p>{new Date(row.fecha_programada).toLocaleString()}</p><p>{row.descripcion}</p><p className="text-sm text-slate-600">Responsable: {row.responsable_nombre}</p>
      {can('disciplina','editar')&&!op.denied&&<div className="flex flex-wrap gap-2">
        {row.estado==='PENDIENTE'&&<button className="wf-secondary" disabled={op.busy} onClick={()=>setForm(row)}>Editar citación {row.id}</button>}
        {(row.estado==='PENDIENTE'?['ENTREGADA','ATENDIDA']:row.estado==='ENTREGADA'?['ATENDIDA']:[]).map(state=><button className="wf-secondary" disabled={op.busy} key={state} onClick={()=>void op.run(()=>cambiarEstadoCitacion(row.id,state),()=>{setVersion(v=>v+1);onSuccess(`Citación ${state.toLowerCase()}.`)})}>Marcar {state.toLowerCase()}</button>)}
      </div>}
    </article>)}
    <Pages page={page} count={data.count} onChange={setPage}/>
  </section>
}

function CitationForm({incident,initial,onDone,onCancel}:{incident:Incidente;initial?:Citacion;onDone:()=>void;onCancel:()=>void}) {
  const date=initial?new Date(initial.fecha_programada):null
  const [form,setForm]=useState({tutor_estudiante:initial?.tutor_estudiante.toString()??'',fecha:date?new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16):'',descripcion:initial?.descripcion??''})
  const [page,setPage]=useState(1)
  const tutors=usePaged<TutorDisciplina>('/estudiantes/tutores-disciplina/',{historial_inscripcion:incident.historial_inscripcion,page})
  const op=useOperation()
  return <form className="wf-form rounded-xl bg-slate-50 p-4" onSubmit={e=>{e.preventDefault();void op.run(()=>guardarCitacion({incidente:incident.id,tutor_estudiante:Number(form.tutor_estudiante),fecha_programada:new Date(form.fecha).toISOString(),descripcion:form.descripcion},initial?.id),onDone)}}>
    <h2>{initial?'Editar citación':'Datos de la citación'}</h2><Errors errors={op.errors}/><Status loading={tutors.loading} error={tutors.error} empty={!tutors.items.length}/>
    <fieldset className="grid gap-4 sm:grid-cols-2" disabled={op.busy||op.denied}>
      <Field label="Tutor *" error={op.errors.tutor_estudiante}><select className="wf-input" required value={form.tutor_estudiante} onChange={e=>setForm({...form,tutor_estudiante:e.target.value})}><option value="">Seleccione tutor</option>{initial&&!tutors.items.some(t=>t.id===initial.tutor_estudiante)&&<option value={initial.tutor_estudiante}>{initial.tutor_nombre}</option>}{tutors.items.map(t=><option key={t.id} value={t.id}>{t.nombre}</option>)}</select></Field>
      <Field label="Fecha de citación *" error={op.errors.fecha_programada}><input className="wf-input" type="datetime-local" required value={form.fecha} onChange={e=>setForm({...form,fecha:e.target.value})}/></Field>
      <Field label="Descripción de citación"><textarea className="wf-input" value={form.descripcion} onChange={e=>setForm({...form,descripcion:e.target.value})}/></Field>
    </fieldset>
    {tutors.count>20&&<Pages page={page} count={tutors.count} onChange={setPage}/>}
    <div className="flex gap-3"><button className="wf-primary" disabled={op.busy||op.denied||tutors.loading}>Guardar citación</button><button className="wf-secondary" type="button" disabled={op.busy} onClick={onCancel}>Cancelar citación</button></div>
  </form>
}

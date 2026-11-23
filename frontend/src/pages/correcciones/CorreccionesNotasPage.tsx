import { useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import { resolverCorreccion,type Correccion } from '../../api/schoolWorkflows'
import { useOperation,usePaged } from '../workflows/useWorkflow'
import { Errors,Field,Pages,Status } from '../workflows/WorkflowUI'
import SolicitudCorreccionForm from './SolicitudCorreccionForm'
import '../workflows/workflows.css'

export default function CorreccionesNotasPage() {
  const {can,isProfesor,user}=useAuth()
  const [version,setVersion]=useState(0),[page,setPage]=useState(1),[state,setState]=useState(''),[form,setForm]=useState(false),[success,setSuccess]=useState('')
  const [resolution,setResolution]=useState<{row:Correccion;approve:boolean}|null>(null)
  const op=useOperation()
  const data=usePaged<Correccion>('/academico/correcciones/',{estado:state,page},version)
  const approve=can('correccion-nota','editar')&&!op.denied
  const reload=()=>setVersion(v=>v+1)
  return <main className="wf-page space-y-6">
    <header className="flex flex-wrap justify-between gap-4"><div><h1>Correcciones de notas</h1><p className="mt-2 text-slate-600">Solicitudes, autorización y trazabilidad de calificaciones cerradas.</p></div>{isProfesor()&&can('correccion-nota','crear')&&!form&&<button className="wf-primary self-start" onClick={()=>{setForm(true);setSuccess('')}}>Nueva solicitud</button>}</header>
    {success&&<p role="status" className="wf-success">{success}</p>}
    <Errors errors={op.errors}/>
    {op.denied&&<p className="text-sm text-slate-600">Sus permisos cambiaron. Recargue la sesión antes de intentar otra acción.</p>}
    {form&&<SolicitudCorreccionForm onCancel={()=>setForm(false)} onDone={()=>{setForm(false);setSuccess('Solicitud registrada.');reload()}}/>}
    <section className="wf-card flex flex-wrap items-end gap-3"><div className="min-w-0 flex-1"><Field label="Estado de solicitud"><select className="wf-input" value={state} onChange={e=>{setState(e.target.value);setPage(1);setResolution(null);setSuccess('')}}><option value="">Todos los estados</option><option value="SOLICITADA">Pendientes</option><option value="APROBADA">Aprobadas</option><option value="RECHAZADA">Rechazadas</option></select></Field></div><button className="wf-secondary" onClick={reload}>Actualizar</button></section>
    {resolution&&!op.denied&&<section aria-label="Confirmar resolución" className="wf-card space-y-4 border-brand-300">
      <h2>{resolution.approve?'Aprobar corrección':'Rechazar corrección'} #{resolution.row.id}</h2>
      <p>{resolution.row.detalle_calificacion.estudiante_nombre} · {resolution.row.detalle_calificacion.actividad_nombre}</p>
      <p>{resolution.row.valor_anterior} → <strong>{resolution.row.valor_nuevo}</strong></p>
      <p>{resolution.approve?'La aprobación actualizará la nota y recalculará sus resultados. Si faltan datos, no se aplicará ningún cambio.':'La nota permanecerá sin cambios. La solicitud quedará rechazada.'}</p>
      <div className="flex flex-wrap gap-3"><button className="wf-primary" disabled={op.busy} onClick={()=>{setSuccess('');void op.run(()=>resolverCorreccion(resolution.row.id,resolution.approve),()=>{setSuccess(resolution.approve?'Corrección aprobada.':'Solicitud rechazada.');setResolution(null);reload()},status=>{if(status===409){setResolution(null);reload()}})}}>{op.busy?'Procesando...':resolution.approve?'Confirmar aprobación':'Confirmar rechazo'}</button><button className="wf-secondary" disabled={op.busy} onClick={()=>setResolution(null)}>Cancelar resolución</button></div>
    </section>}
    <Status loading={data.loading} error={data.error} empty={!data.items.length}/>
    {data.items.map(row=><article className="wf-card space-y-3" key={row.id}>
      <div className="flex flex-wrap justify-between gap-3"><h2>{row.detalle_calificacion.estudiante_nombre}</h2><span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold">{row.estado}</span></div>
      <p className="text-sm text-slate-600">{row.detalle_calificacion.curso_nombre} · {row.detalle_calificacion.materia_nombre} · {row.detalle_calificacion.actividad_nombre} · {row.detalle_calificacion.periodo_nombre}</p>
      <div className="flex flex-wrap gap-8 rounded-xl bg-slate-50 p-4"><div><p className="text-sm text-slate-600">Nota anterior</p><p className="text-2xl font-semibold">{row.valor_anterior}</p></div><div><p className="text-sm text-slate-600">Nota propuesta</p><p className="text-2xl font-semibold text-brand-700">{row.valor_nuevo}</p></div></div>
      <p><strong>Motivo:</strong> {row.motivo}</p><p className="text-sm text-slate-600">Solicitante: {row.solicitante_nombre} · {new Date(row.solicitado_at).toLocaleString()}</p>
      {row.resuelto_at&&<p className="text-sm text-slate-600">Resuelto por: {row.autorizador_nombre} · {new Date(row.resuelto_at).toLocaleString()}</p>}
      {row.estado==='SOLICITADA'&&approve&&row.solicitado_por!==user?.id&&<div className="flex flex-wrap gap-3"><button className="wf-primary" aria-label={`Aprobar solicitud ${row.id}`} disabled={op.busy} onClick={()=>{setResolution({row,approve:true});setSuccess('')}}>Aprobar</button><button className="wf-secondary" aria-label={`Rechazar solicitud ${row.id}`} disabled={op.busy} onClick={()=>{setResolution({row,approve:false});setSuccess('')}}>Rechazar</button></div>}
    </article>)}
    <Pages page={page} count={data.count} onChange={p=>{setPage(p);setResolution(null)}}/>
  </main>
}

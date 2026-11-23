import { useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import type { Incidente,InscripcionDisciplina } from '../../api/schoolWorkflows'
import { usePaged } from '../workflows/useWorkflow'
import { Field,Pages,Status } from '../workflows/WorkflowUI'
import IncidenteForm from './IncidenteForm'
import CitacionesPanel from './CitacionesPanel'
import '../workflows/workflows.css'

export default function DisciplinaPage() {
  const {can}=useAuth()
  const [search,setSearch]=useState(''),[applied,setApplied]=useState(''),[catalogPage,setCatalogPage]=useState(1)
  const [selection,setSelection]=useState<InscripcionDisciplina|null>(null),[page,setPage]=useState(1),[version,setVersion]=useState(0)
  const [editing,setEditing]=useState<Incidente|true|null>(null),[citations,setCitations]=useState<Incidente|null>(null),[success,setSuccess]=useState('')
  const [filters,setFilters]=useState({estado:'',desde:'',hasta:'',gestion:''})
  const catalog=usePaged<InscripcionDisciplina>('/estudiantes/inscripciones-disciplina/',{search:applied,page:catalogPage})
  const data=usePaged<Incidente>('/estudiantes/incidentes/',{...filters,estudiante:selection?.estudiante??'',page},version,Boolean(selection))
  const saved=()=>{setEditing(null);setVersion(v=>v+1);setSuccess('Observación guardada.')}
  return <main className="wf-page space-y-6">
    <header><h1>Disciplina y citaciones</h1><p className="mt-2 text-slate-600">Observaciones, historial del estudiante y seguimiento de citaciones.</p></header>
    {success&&<p role="status" className="wf-success">{success}</p>}
    <section className="wf-card space-y-4">
      <form className="flex flex-wrap items-end gap-3" onSubmit={e=>{e.preventDefault();setApplied(search);setCatalogPage(1)}}><div className="min-w-0 flex-1"><Field label="Buscar estudiante"><input className="wf-input" value={search} onChange={e=>setSearch(e.target.value)}/></Field></div><button className="wf-secondary">Buscar</button></form>
      <Status loading={catalog.loading} error={catalog.error} empty={!catalog.items.length}/>
      {!catalog.loading&&!catalog.error&&<Field label="Inscripción"><select className="wf-input" value={selection?.id??''} onChange={e=>{setSelection(catalog.items.find(i=>i.id===Number(e.target.value))??null);setPage(1);setEditing(null);setCitations(null);setSuccess('')}}><option value="">Seleccione estudiante e inscripción</option>{selection&&!catalog.items.some(i=>i.id===selection.id)&&<option value={selection.id}>{selection.estudiante_nombre} · {selection.curso_nombre}</option>}{catalog.items.map(i=><option key={i.id} value={i.id}>{i.estudiante_nombre} · {i.curso_nombre}</option>)}</select></Field>}
      {catalog.count>20&&<Pages page={catalogPage} count={catalog.count} onChange={setCatalogPage}/>}
    </section>
    {selection&&<>
      <div className="flex flex-wrap items-center justify-between gap-3"><h2>Historial de {selection.estudiante_nombre}</h2>{can('disciplina','crear')&&!editing&&<button className="wf-primary" onClick={()=>{setEditing(true);setSuccess('')}}>Nueva observación</button>}</div>
      {editing&&<IncidenteForm key={editing===true?`new-${selection.id}`:editing.id} enrollment={editing===true?selection.id:editing.historial_inscripcion} initial={editing===true?undefined:editing} onDone={saved} onCancel={()=>setEditing(null)}/>}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Estado de incidente"><select className="wf-input" value={filters.estado} onChange={e=>{setFilters({...filters,estado:e.target.value});setPage(1)}}><option value="">Todos</option><option>ABIERTO</option><option>CERRADO</option></select></Field>
        <Field label="Desde"><input className="wf-input" type="date" value={filters.desde} onChange={e=>{setFilters({...filters,desde:e.target.value});setPage(1)}}/></Field>
        <Field label="Hasta"><input className="wf-input" type="date" value={filters.hasta} onChange={e=>{setFilters({...filters,hasta:e.target.value});setPage(1)}}/></Field>
        <Field label="Año del incidente"><input className="wf-input" type="number" min="1900" max="9999" value={filters.gestion} onChange={e=>{setFilters({...filters,gestion:e.target.value});setPage(1)}}/></Field>
      </section>
      <Status loading={data.loading} error={data.error} empty={!data.items.length}/>
      {data.items.map(row=><article className="wf-card space-y-3" key={row.id}>
        <div className="flex flex-wrap justify-between gap-2"><p className="font-semibold">{row.tipo} · {row.severidad}</p><span className="rounded-full bg-slate-100 px-3 py-1 text-sm">{row.estado}</span></div>
        <p>{row.descripcion}</p><p className="text-sm text-slate-600">{new Date(row.fecha).toLocaleString()} · {row.curso_nombre} · Responsable: {row.responsable_nombre}</p>
        <div className="flex flex-wrap gap-3">{can('disciplina','editar')&&<button className="wf-secondary" onClick={()=>setEditing(row)}>Editar incidente {row.id}</button>}<button className="wf-secondary" aria-label={`Citaciones del incidente ${row.id}`} onClick={()=>setCitations(row)}>Ver citaciones</button></div>
      </article>)}
      <Pages page={page} count={data.count} onChange={setPage}/>
      {citations&&<CitacionesPanel key={citations.id} incident={citations} onClose={()=>setCitations(null)} onSuccess={setSuccess}/>}
    </>}
  </main>
}

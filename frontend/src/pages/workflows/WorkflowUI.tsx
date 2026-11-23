import type { ReactNode } from 'react'

export function Field({label,error,children}:{label:string;error?:string;children:ReactNode}) {
  return <label className="grid gap-1.5 text-sm font-medium text-slate-700"><span>{label}</span>{children}{error&&<span role="alert" className="text-red-700">{error}</span>}</label>
}
export function Errors({errors}:{errors:Record<string,string>}) {
  const entries=Object.entries(errors)
  return entries.length>0?<div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{entries.map(([key,value])=><p key={key}>{key==='detail'||key==='non_field_errors'?'':`${key}: `}{value}</p>)}</div>:null
}
export function Pages({page,count,onChange}:{page:number;count:number;onChange:(page:number)=>void}) {
  return <nav aria-label="Paginación" className="flex flex-wrap items-center gap-3 text-sm"><button type="button" className="wf-secondary" disabled={page<=1} onClick={()=>onChange(page-1)}>Anterior</button><span>Página {page} · {count} registros</span><button type="button" className="wf-secondary" disabled={page*20>=count} onClick={()=>onChange(page+1)}>Siguiente</button></nav>
}
export function Status({loading,error,empty}:{loading:boolean;error:string;empty:boolean}) {
  if(loading)return <p role="status" className="py-5 text-slate-600">Cargando...</p>
  if(error)return <div role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{error}</div>
  if(empty)return <p className="py-5 text-slate-600">Sin registros para esta consulta.</p>
  return null
}

import axiosInstance from './axiosInstance'

export type DashboardMetricKey = 'colegios'|'unidades'|'usuarios'|'docentes'|'estudiantes'|'tutores'|'cursos'|'asignaciones'
const endpoints: Record<DashboardMetricKey,string> = {
  colegios:'/institucion/colegios/', unidades:'/institucion/unidades-educativas/', usuarios:'/usuarios/usuarios/',
  docentes:'/personal/profesores/', estudiantes:'/estudiantes/estudiantes/', tutores:'/estudiantes/tutores/',
  cursos:'/academico/cursos/', asignaciones:'/academico/asignaciones-docentes/',
}
export interface MetricResult { key:DashboardMetricKey; value?:number; restricted?:boolean; error?:boolean }
export interface RecentAudit { id:number; accion:string; entidad:string; ambito:string; created_at:string }

export async function loadDashboardMetrics(keys:DashboardMetricKey[],signal?:AbortSignal):Promise<MetricResult[]> {
  const settled=await Promise.allSettled(keys.map(async key=>{
    const {data}=await axiosInstance.get(endpoints[key],{params:{page:1,page_size:1},signal})
    const value=Array.isArray(data)?data.length:(typeof data?.count==='number'?data.count:undefined)
    return {key,value} as MetricResult
  }))
  return settled.map((result,index)=>result.status==='fulfilled'?result.value:{key:keys[index],error:true,restricted:(result.reason?.response?.status===403)})
}
export async function loadRecentAudit(signal?:AbortSignal) {
  const {data}=await axiosInstance.get<RecentAudit[]|{results?:RecentAudit[]}>('/usuarios/auditoria/',{params:{page:1,page_size:5},signal})
  // El endpoint normalmente es paginado, pero también toleramos una lista para
  // mantener el panel compatible con respuestas institucionales ya existentes.
  return Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : []
}


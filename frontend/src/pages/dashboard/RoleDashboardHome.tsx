import { BookOpenCheck, Building2, GraduationCap, School, Users } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import { buildNavigation, resolveVisualProfile } from '../../app/navigation/navigationConfig'
import type { VisualProfile } from '../../app/navigation/types'
import { loadDashboardMetrics, loadRecentAudit, type DashboardMetricKey, type MetricResult, type RecentAudit } from '../../api/dashboard'
import { rutaModuloEnPortal } from './modules'
import { DashboardEmptyState, DashboardErrorState, DashboardMetricCard, DashboardQuickAction, DashboardSection, InstitutionalIdentity } from './components/DashboardComponents'

const configs:Record<string,{title:string;description:string;metrics:DashboardMetricKey[];audit:boolean}>={
  SUPERADMIN:{title:'Panel Super Administrador',description:'Administración global de la plataforma',metrics:['colegios','unidades','usuarios'],audit:true},
  ADMINISTRADOR_INSTITUCIONAL:{title:'Administración institucional',description:'Resumen operativo del colegio y la unidad educativa.',metrics:['usuarios','docentes','estudiantes','cursos','asignaciones'],audit:true},
  DIRECTOR:{title:'Panel de Dirección',description:'Gestión académica de todas las unidades del colegio.',metrics:['docentes','estudiantes','cursos','asignaciones'],audit:true},
  SECRETARIA:{title:'Panel de Secretaría',description:'Matrícula, estudiantes y organización de la unidad.',metrics:['docentes','estudiantes','tutores','asignaciones'],audit:false},
  TESORERIA:{title:'Panel de Tesorería',description:'Perfil institucional. Los módulos estarán disponibles cuando se configuren permisos funcionales.',metrics:[],audit:false},
}
const labels:Record<DashboardMetricKey,string>={colegios:'Colegios',unidades:'Unidades educativas',usuarios:'Usuarios',docentes:'Docentes',estudiantes:'Estudiantes',tutores:'Tutores',cursos:'Cursos',asignaciones:'Asignaciones docentes'}
const icons:Record<DashboardMetricKey,typeof Users>={colegios:Building2,unidades:School,usuarios:Users,docentes:Users,estudiantes:GraduationCap,tutores:Users,cursos:BookOpenCheck,asignaciones:BookOpenCheck}

export default function RoleDashboardHome({profile,basePath}:{profile?:VisualProfile;basePath:string}) {
  const {user,can}=useAuth(), actual=profile??resolveVisualProfile(user), config=configs[actual]
  const [metrics,setMetrics]=useState<MetricResult[]>([]),[audit,setAudit]=useState<RecentAudit[]>([]),[loading,setLoading]=useState(true),[auditError,setAuditError]=useState(false)
  const modules=useMemo(()=>buildNavigation(user,can).flatMap(g=>g.modulos),[user,can])
  const quickModules=useMemo(()=>[...modules].sort((a,b)=>Number(b.key==='panel-institucional')-Number(a.key==='panel-institucional')||Number(Boolean(b.directa))-Number(Boolean(a.directa))).slice(0,4),[modules])
  const puedeAuditoria=Boolean(config?.audit&&can('auditoria','listar'))
  useEffect(()=>{if(!config)return;const controller=new AbortController();void loadDashboardMetrics(config.metrics,controller.signal).then(setMetrics).finally(()=>setLoading(false));if(puedeAuditoria)void loadRecentAudit(controller.signal).then(setAudit).catch(error=>{if(error?.code!=='ERR_CANCELED'&&error?.name!=='CanceledError')setAuditError(true)});return()=>controller.abort()},[config,puedeAuditoria])
  if(!config)return <DashboardErrorState restricted/>
  const scopeText=actual==='DIRECTOR'||(actual==='TESORERIA'&&user?.alcance?.tipo==='COLEGIO')?'Alcance: todo el colegio':actual==='SECRETARIA'||(actual==='TESORERIA'&&user?.alcance?.tipo==='UNIDAD')?'Alcance: unidad educativa asignada':undefined
  return <div className="px-4 py-7 sm:px-6 lg:px-8"><InstitutionalIdentity title={config.title} description={config.description} global={actual==='SUPERADMIN'} college={user?.alcance?.colegio_nombre??user?.unidad?.colegio?.nombre} unit={actual==='DIRECTOR'?undefined:user?.alcance?.unidad_nombre??user?.unidad?.nombre} role={user?.perfil?.puesto?.nombre??user?.rol.nombre} scopeText={scopeText}/>
    <DashboardSection title="Resumen"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{config.metrics.map(key=>{const r=metrics.find(x=>x.key===key);return <DashboardMetricCard key={key} title={labels[key]} description="Registros disponibles en su ámbito" icon={icons[key]} loading={loading} value={r?.value} error={r?.error}/>})}</div></DashboardSection>
    <DashboardSection title="Acciones frecuentes" description={`${modules.length} módulos funcionales disponibles`}><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{quickModules.map(m=><DashboardQuickAction key={m.key} title={m.titulo} description={m.descripcion} to={rutaModuloEnPortal(m,basePath)} icon={m.icono}/>)}</div></DashboardSection>
    {puedeAuditoria&&<DashboardSection title="Actividad de seguridad">{auditError?<DashboardErrorState/>:audit.length?<div className="overflow-x-auto rounded-2xl bg-white shadow-sm"><table className="w-full text-left text-sm"><thead><tr>{['Fecha','Acción','Entidad','Ámbito'].map(x=><th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{audit.map(e=><tr key={e.id} className="border-t"><td className="px-4 py-3">{new Date(e.created_at).toLocaleString()}</td><td className="px-4 py-3">{e.accion}</td><td className="px-4 py-3">{e.entidad}</td><td className="px-4 py-3">{e.ambito}</td></tr>)}</tbody></table></div>:!loading&&<DashboardEmptyState/>}</DashboardSection>}
  </div>
}

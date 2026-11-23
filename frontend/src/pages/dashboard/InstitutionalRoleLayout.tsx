import { useAuth } from '../../app/contexts/AuthContext'
import { buildNavigation } from '../../app/navigation/navigationConfig'
import RoleLayout from './RoleLayout'

export default function InstitutionalRoleLayout({basePath,title}:{basePath:string;title:string}) {
  const {user,can}=useAuth()
  const subtitulo=user?.alcance?.tipo==='COLEGIO'
    ? `${user.alcance.colegio_nombre??'Colegio'} · Alcance: todo el colegio`
    : `${user?.alcance?.colegio_nombre??user?.unidad?.colegio?.nombre??'Colegio'} · ${user?.alcance?.unidad_nombre??user?.unidad?.nombre??'Unidad'} · Alcance: unidad educativa asignada`
  return <RoleLayout basePath={basePath} titulo={title} subtitulo={subtitulo} modulos={buildNavigation(user,can).flatMap(g=>g.modulos)}/>
}

import { ArrowRight, School } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../app/contexts/AuthContext'
import type { ModuloPanel } from './modules'
import { rutaModuloEnPortal } from './modules'

export default function PortalInicio({ titulo, descripcion, basePath, modulos }: {
  titulo: string
  descripcion: string
  basePath: string
  modulos: ModuloPanel[]
}) {
  const { user } = useAuth()
  return <div className="px-4 py-8 sm:px-6 lg:px-8">
    <section className="rounded-3xl bg-gradient-to-r from-brand-900 via-brand-800 to-brand-700 px-7 py-9 text-white shadow-xl">
      <p className="text-sm font-bold uppercase tracking-[0.2em] text-brand-200">{user?.unidad?.colegio?.nombre ?? 'Sistema educativo'}</p>
      <h1 className="mt-2 text-3xl font-bold sm:text-4xl">{titulo}</h1>
      <p className="mt-3 max-w-2xl text-brand-100">{descripcion}</p>
      {user?.unidad && <p className="mt-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm"><School size={17} />{user.unidad.nombre}</p>}
    </section>
    {modulos.length > 0 && <section className="mt-8"><div className="mb-4"><h2 className="text-xl font-bold">Acciones rápidas</h2><p className="text-sm text-slate-500">{modulos.length} módulos disponibles según su perfil y permisos.</p></div><div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
      {modulos.slice(0, 3).map((modulo) => {
        const Icono = modulo.icono
        return <Link key={modulo.ruta} to={rutaModuloEnPortal(modulo, basePath)} className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
          <span className={`flex h-12 w-12 items-center justify-center rounded-xl ${modulo.color}`}><Icono size={24} /></span>
          <h2 className="mt-4 text-lg font-bold text-slate-900">{modulo.titulo}</h2>
          <p className="mt-2 text-sm text-slate-600">{modulo.descripcion}</p>
          <span className="mt-5 flex items-center gap-2 text-sm font-bold text-brand-700">Abrir módulo <ArrowRight size={17} /></span>
        </Link>
      })}
    </div></section>}
  </div>
}

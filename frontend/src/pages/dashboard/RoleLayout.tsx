import { ChevronDown, ChevronsLeft, ChevronsRight, DatabaseBackup, Home, LogOut, Menu, School, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../app/contexts/AuthContext'
import { NOMBRE_SISTEMA } from '../../app/config/branding'
import { NAVIGATION_GROUPS } from '../../app/navigation/moduleCatalog'
import type { NavigationModule } from '../../app/navigation/types'
import type { ModuloPanel } from './modules'
import { rutaModuloEnPortal } from './modules'

export default function RoleLayout({ basePath, titulo, subtitulo, modulos }: { basePath: string; titulo: string; subtitulo: string; modulos: ModuloPanel[] }) {
  const [abierto, setAbierto] = useState(true)
  const [movilAbierto, setMovilAbierto] = useState(false)
  const [colapsados, setColapsados] = useState<Record<string, boolean>>({})
  const { user, logout, isSuperAdmin } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const grupos = useMemo(() => NAVIGATION_GROUPS.map(grupo => ({ ...grupo, modulos: modulos.filter(modulo => (modulo as NavigationModule).grupo === grupo.key) })).filter(grupo => grupo.modulos.length), [modulos])
  const moduloActivo = modulos.find(modulo => location.pathname === rutaModuloEnPortal(modulo, basePath) || location.pathname.startsWith(`${rutaModuloEnPortal(modulo, basePath)}/`))
  const respaldoActivo = location.pathname === '/dashboard/superadmin/respaldos'

  useEffect(() => {
    if (!movilAbierto) return
    const cerrar = (event: KeyboardEvent) => { if (event.key === 'Escape') setMovilAbierto(false) }
    window.addEventListener('keydown', cerrar)
    return () => window.removeEventListener('keydown', cerrar)
  }, [movilAbierto])

  const cerrarSesion = async () => { await logout(); navigate('/login', { replace: true }) }
  return <div className="min-h-screen bg-[#f6f5f0] text-slate-900">
    <a href="#contenido-panel" className="sr-only z-[70] rounded-lg bg-white p-3 focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Ir al contenido</a>
    {movilAbierto && <button type="button" aria-label="Cerrar menú" onClick={() => setMovilAbierto(false)} className="fixed inset-0 z-40 bg-slate-950/50 md:hidden"/>}
    <aside aria-label="Navegación principal" className={`fixed inset-y-0 left-0 z-50 flex flex-col border-r border-brand-800 bg-brand-950 text-brand-50 shadow-xl transition-all ${abierto ? 'md:w-64' : 'md:w-20'} ${movilAbierto ? 'w-72 translate-x-0' : 'w-72 -translate-x-full md:translate-x-0'}`}>
      <div className="flex h-20 shrink-0 items-center border-b border-white/10 px-4">
        <Link to={basePath} aria-label="Ir al inicio" className="flex min-w-0 items-center gap-3 text-white">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/20 bg-white/10 text-white"><School size={24}/></span>
          {abierto && <span className="min-w-0"><span className="block whitespace-nowrap text-base font-bold">{NOMBRE_SISTEMA}</span><span className="block text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-brand-200">Gestión escolar SaaS</span></span>}
        </Link>
        <button type="button" aria-label="Cerrar menú" onClick={() => setMovilAbierto(false)} className="ml-auto rounded-lg p-2 text-white md:hidden"><X size={20}/></button>
      </div>
      <nav className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        <NavLink to={basePath} end aria-label="Inicio" onClick={() => setMovilAbierto(false)} className={({ isActive }) => enlaceMenu(isActive, abierto)}><Home size={20}/>{abierto && <span>Inicio</span>}</NavLink>
        {isSuperAdmin() && <NavLink to="/dashboard/superadmin/respaldos" aria-label="Respaldos" onClick={() => setMovilAbierto(false)} className={({ isActive }) => enlaceMenu(isActive, abierto)}><DatabaseBackup size={20}/>{abierto && <span>Respaldos</span>}</NavLink>}
        {grupos.map(grupo => {
          const activo = grupo.modulos.some(modulo => modulo === moduloActivo)
          const expandido = activo || !colapsados[grupo.key]
          return <section key={grupo.key} className="mt-4">
            {abierto && <button type="button" aria-expanded={expandido} onClick={() => setColapsados(value => ({ ...value, [grupo.key]: expandido }))} className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-[0.65rem] font-bold uppercase tracking-[0.12em] text-brand-200"><span>{grupo.nombre}</span><ChevronDown size={15} className={`transition ${expandido ? 'rotate-180' : ''}`}/></button>}
            {(expandido || !abierto) && <div className="space-y-1">{grupo.modulos.map(modulo => {
              const Icono = modulo.icono
              return <NavLink key={modulo.ruta} to={rutaModuloEnPortal(modulo, basePath)} onClick={() => setMovilAbierto(false)} title={!abierto ? modulo.titulo : undefined} className={({ isActive }) => enlaceMenu(isActive, abierto)}><Icono size={19}/>{abierto && <span className="truncate">{modulo.titulo}</span>}</NavLink>
            })}</div>}
          </section>
        })}
      </nav>
      <div className="shrink-0 border-t border-white/10 p-3"><button type="button" aria-label="Cerrar sesión" onClick={() => void cerrarSesion()} className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-sm font-semibold text-brand-100 hover:bg-white/10 ${abierto ? '' : 'justify-center'}`}><LogOut size={20}/>{abierto && <span>Cerrar sesión</span>}</button></div>
    </aside>
    <div className={`min-h-screen transition-[margin] ${abierto ? 'md:ml-64' : 'md:ml-20'}`}>
      <header className="sticky top-0 z-30 border-b border-[#dce3dc] bg-white/95 px-4 py-3 backdrop-blur sm:px-6">
        <div className="flex min-h-12 items-center gap-3">
          <button type="button" aria-label="Abrir menú" onClick={() => setMovilAbierto(true)} className="rounded-lg p-2 text-brand-800 md:hidden"><Menu size={23}/></button>
          <button type="button" onClick={() => setAbierto(value => !value)} className="hidden rounded-lg p-2 text-brand-800 hover:bg-brand-50 md:block" aria-label={abierto ? 'Contraer menú' : 'Expandir menú'}>{abierto ? <ChevronsLeft size={21}/> : <ChevronsRight size={21}/>}</button>
          <div className="min-w-0"><p className="truncate text-sm font-bold text-[#172a25] sm:text-base">{titulo}</p><p className="truncate text-xs text-slate-500">{subtitulo}</p></div>
          <div className="ml-auto min-w-0 text-right"><p className="truncate text-sm font-semibold">{user ? `${user.nombre} ${user.apellido}` : 'Usuario'}</p><p className="truncate text-xs text-brand-700">{user?.perfil?.puesto?.nombre ?? user?.rol?.nombre}</p></div>
          <div id="appearance-slot" className="shrink-0" />
          <span aria-hidden="true" className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-800 sm:flex">{user?.nombre?.charAt(0)?.toUpperCase() ?? 'U'}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2 text-xs text-slate-500"><Link to={basePath}>Inicio</Link>{(moduloActivo || respaldoActivo) && <><span>/</span><span aria-current="page" className="font-semibold text-slate-700">{moduloActivo?.titulo ?? 'Respaldos'}</span></>}{user?.unidad && <span className="ml-auto truncate">{user.unidad.colegio?.nombre} — {user.unidad.nombre}</span>}</div>
      </header>
      <main id="contenido-panel" className="workspace-main min-h-[calc(100vh-5rem)]"><Outlet/></main>
    </div>
  </div>
}

function enlaceMenu(activo: boolean, abierto: boolean) {
  return `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition ${abierto ? '' : 'justify-center'} ${activo ? 'bg-brand-700 text-white shadow-sm' : 'text-brand-100 hover:bg-white/10 hover:text-white'}`
}

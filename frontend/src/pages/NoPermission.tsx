import { Link } from 'react-router-dom'
import { dashboardPath } from '../app/routes/dashboardPath'
import { useAuth } from '../app/contexts/AuthContext'

export default function NoPermission() {
  const { user, logout } = useAuth()
  return <main className="flex min-h-screen items-center justify-center bg-slate-100 p-5">
    <section className="w-full max-w-lg rounded-2xl bg-white p-8 text-center shadow-xl">
      <h1 className="text-2xl font-bold text-slate-900">Acceso no disponible</h1>
      <p className="mt-3 text-slate-600">Su cuenta no tiene permisos para abrir esta sección. Consulte con el administrador de su institución.</p>
      <div className="mt-7 flex justify-center gap-3">
        <Link to={dashboardPath(user)} className="rounded-xl bg-brand-700 px-5 py-3 font-semibold text-white">Volver a mi panel</Link>
        <button type="button" onClick={() => void logout()} className="rounded-xl border border-slate-300 px-5 py-3 font-semibold text-slate-700">Cerrar sesión</button>
      </div>
    </section>
  </main>
}

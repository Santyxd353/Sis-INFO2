import { isAxiosError } from 'axios'
import { ArrowLeft, Eye, EyeOff, GraduationCap, LockKeyhole, School, User } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../app/contexts/AuthContext'
import { dashboardPath } from '../app/routes/dashboardPath'
import { resolveVisualProfile } from '../app/navigation/navigationConfig'
import { DESCRIPCION_SISTEMA, NOMBRE_SISTEMA } from '../app/config/branding'

export default function Login() {
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [mostrarPassword, setMostrarPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()

  const iniciarSesion = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setCargando(true)

    try {
      const user = await login(identifier, password)
      const from = location.state?.from
      const stripe = from?.pathname === '/dashboard/suscripciones' ? new URLSearchParams(from.search).get('stripe') : null
      const retornoStripe = stripe === 'confirmacion' || stripe === 'cancelado' ? `/dashboard/suscripciones?stripe=${stripe}` : null
      const planSeleccionado = localStorage.getItem('plan_seleccionado')
      const esDirector = resolveVisualProfile(user) === 'DIRECTOR'
      if (planSeleccionado && !esDirector) localStorage.removeItem('plan_seleccionado')
      const destino = planSeleccionado && esDirector ? '/dashboard/suscripciones' : dashboardPath(user)
      navigate(retornoStripe ?? destino, { replace: true })
    } catch (err: unknown) {
      if (isAxiosError(err)) {
        const data = err.response?.data as { error?: string; detail?: string } | undefined
        if (!err.response) setError('No se pudo conectar con el servidor. Intente nuevamente.')
        else if (err.response.status === 403) setError('Su usuario no tiene permiso para acceder.')
        else setError(data?.error ?? data?.detail ?? 'Correo, usuario o contraseña incorrectos.')
      } else {
        setError(err instanceof Error ? err.message : 'No se pudo iniciar sesión.')
      }
    } finally {
      setCargando(false)
    }
  }

  return (
    <main className="grid min-h-screen bg-[#f6f5f0] lg:grid-cols-2">
      <section className="relative hidden overflow-hidden bg-brand-950 p-12 text-white lg:flex lg:flex-col lg:justify-between xl:p-16">
        <div className="absolute -right-32 -top-28 h-96 w-96 rounded-full border border-white/10" />
        <div className="absolute -bottom-40 -left-20 h-[30rem] w-[30rem] rounded-full border border-white/10" />

        <Link to="/" className="relative flex items-center gap-3 self-start">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/15 backdrop-blur">
            <School size={28} />
          </span>
          <span>
            <span className="block text-xl font-bold">{NOMBRE_SISTEMA}</span>
            <span className="text-sm text-brand-200">{DESCRIPCION_SISTEMA}</span>
          </span>
        </Link>

        <div className="relative max-w-xl">
          <span className="mb-7 flex h-16 w-16 items-center justify-center rounded-full border border-white/25 text-[#d4ba83]">
            <GraduationCap size={36} />
          </span>
          <p className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-brand-200">Tu comunidad educativa</p>
          <h1 className="font-serif text-5xl leading-tight">Un espacio para seguir <em>creciendo.</em></h1>
          <p className="mt-5 text-lg leading-8 text-brand-100">
            Accede a las herramientas de administración académica y continúa acompañando a nuestra
            comunidad educativa.
          </p>
        </div>

        <p className="relative text-sm text-brand-200">Administración educativa centralizada</p>
      </section>

      <section className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md rounded-xl border border-[#dce3dc] bg-white p-6 shadow-sm sm:p-9">
          <Link to="/" className="mb-10 inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-900">
            <ArrowLeft size={18} /> Volver al inicio
          </Link>

          <div className="mb-8 lg:hidden">
            <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-700 text-white">
              <School size={26} />
            </span>
            <p className="font-bold text-brand-900">{NOMBRE_SISTEMA}</p>
          </div>

          <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-brand-700">Bienvenido nuevamente</p>
          <h2 className="font-serif text-4xl tracking-tight text-[#172a25]">Iniciar sesión</h2>
          <p className="mt-3 text-slate-600">Ingrese sus credenciales para acceder al sistema.</p>

          <form onSubmit={iniciarSesion} className="mt-8 space-y-5">
            {error && (
              <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <label className="block text-sm font-semibold text-slate-700">
              Correo electrónico o usuario
              <span className="relative mt-2 block">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                <input
                  type="text"
                  autoComplete="username"
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  placeholder="nombre@colegio.edu o usuario"
                  required
                  className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-11 pr-4 font-normal outline-none transition focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
                />
              </span>
            </label>

            <label className="block text-sm font-semibold text-slate-700">
              Contraseña
              <span className="relative mt-2 block">
                <LockKeyhole className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                <input
                  type={mostrarPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full rounded-xl border border-slate-300 bg-white py-3 pl-11 pr-12 font-normal outline-none transition focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
                />
                <button
                  type="button"
                  onClick={() => setMostrarPassword((actual) => !actual)}
                  aria-label={mostrarPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:bg-slate-100"
                >
                  {mostrarPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </span>
            </label>

            <button
              type="submit"
              disabled={cargando}
              className="flex w-full items-center justify-center rounded-xl bg-brand-700 px-5 py-3.5 font-bold text-white shadow-lg shadow-brand-200 transition hover:bg-brand-800 disabled:cursor-wait disabled:opacity-60"
            >
              {cargando ? 'Ingresando...' : 'Ingresar al sistema'}
            </button>
          </form>

          <p className="mt-8 text-center text-xs leading-5 text-slate-500">
            El acceso está reservado para usuarios autorizados de la institución.
          </p>
        </div>
      </section>
    </main>
  )
}

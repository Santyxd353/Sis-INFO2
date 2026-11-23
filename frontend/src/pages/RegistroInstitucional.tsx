import axios from 'axios'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { authAxios } from '../api/axiosInstance'
import { normalizarPlanes, urlCheckoutStripe, type MetodoPago, type Plan } from '../api/suscripciones'

const inputClass = 'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 focus:border-brand-500'

function Campo({ nombre, etiqueta, type = 'text', required = true, placeholder }: {
  nombre: string; etiqueta: string; type?: string; required?: boolean; placeholder?: string
}) {
  return <label className="block text-sm font-medium">{etiqueta}
    <input className={inputClass} name={nombre} type={type} required={required} placeholder={placeholder}
      pattern={nombre === 'telefono' ? '\\+[1-9][0-9]{6,14}' : undefined}
      title={nombre === 'telefono' ? 'Incluye el signo +, el código del país y el número; por ejemplo +59170000000.' : undefined} />
    {nombre === 'telefono' && <span className="mt-1 block text-xs font-normal text-slate-500">Incluye el código del país, por ejemplo +59170000000.</span>}
  </label>
}

function mensaje(err: unknown) {
  if (!axios.isAxiosError(err) || !err.response?.data) return 'No se pudo completar la solicitud. Inténtalo nuevamente.'
  if (err.response.status === 404) return 'El servidor no tiene disponible el registro institucional. Reinicia el backend actualizado y vuelve a intentarlo.'
  if (typeof err.response.data !== 'object' || Array.isArray(err.response.data)) return 'El servidor devolvió una respuesta inesperada. Inténtalo nuevamente.'
  const data = err.response.data as Record<string, unknown>
  if (typeof data.detail === 'string') return data.detail
  return Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(' ') : String(value)}`).join(' ')
}

export function RegistroInstitucional() {
  const [params] = useSearchParams()
  const [error, setError] = useState('')
  const [registro, setRegistro] = useState<{
    modo_correo?: string; checkout_url?: string; checkout_pendiente?: boolean; qr_simulado_pendiente?: boolean
  } | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [metodos, setMetodos] = useState<MetodoPago[]>([])
  const [planes, setPlanes] = useState<Plan[] | null>(null)
  const [planElegido, setPlanElegido] = useState<string | null>(null)
  const [metodoElegido, setMetodoElegido] = useState('')
  const planDelEnlace = planes?.find((item) => String(item.id) === params.get('plan'))
  const planPorDefecto = planDelEnlace ?? (planes?.length === 1 ? planes[0] : undefined)
  const plan = planElegido === null ? planPorDefecto?.id : Number(planElegido)
  const planSeleccionado = planes?.find((item) => item.id === plan)
  const requierePago = Boolean(planSeleccionado && Number(planSeleccionado.precio) > 0)
  const metodosDisponibles = metodos.filter((metodo) => {
    if (metodo.codigo === 'QR_SIMULADO') return Boolean(planSeleccionado?.qr_simulado_disponible)
    if (metodo.codigo === 'PASARELA') return planSeleccionado?.moneda === 'BOB'
    return true
  })
  const metodoPago = metodosDisponibles.find((metodo) => metodo.codigo === metodoElegido)?.codigo
    ?? metodosDisponibles.find((metodo) => metodo.codigo === 'STRIPE')?.codigo
    ?? metodosDisponibles[0]?.codigo ?? ''
  const checkout = urlCheckoutStripe(registro?.checkout_url)

  useEffect(() => {
    void authAxios.get<MetodoPago[]>('/suscripciones/metodos-pago-publicos/')
      .then(({ data }) => setMetodos(data.filter((metodo) => metodo.codigo !== 'TARJETA' && metodo.disponible !== false)))
      .catch(() => setMetodos([]))
    void authAxios.get<Plan[] | { count: number; results: Plan[] }>('/suscripciones/planes-publicos/')
      .then(({ data }) => setPlanes(normalizarPlanes(data)))
      .catch(() => setPlanes([]))
  }, [])

  async function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (ocupado || planes === null) return
    if (requierePago && !metodoPago) {
      setError('No hay métodos de pago disponibles para este plan. Puedes elegir el plan más adelante desde Suscripciones.')
      return
    }
    setError(''); setOcupado(true)
    const form = new FormData(event.currentTarget)
    const data = Object.fromEntries(form.entries())
    if (requierePago && metodoPago !== 'STRIPE' && metodoPago !== 'QR_SIMULADO') {
      data.pago_referencia = `ALTA-${metodoPago}-${crypto.randomUUID().slice(0, 8)}`
    }
    if (requierePago) data.metodo_pago = metodoPago
    try {
      const result = await authAxios.post<NonNullable<typeof registro>>('/usuarios/registro-institucional/', {
        ...data, acepta_condiciones: form.has('acepta_condiciones'), ...(plan ? { plan } : {}),
      }, { timeout: 35000 })
      setRegistro(result.data)
      if (plan) {
        try { localStorage.setItem('plan_seleccionado', String(plan)) }
        catch { /* La selección ya quedó guardada en el registro. */ }
      }
    } catch (err) { setError(mensaje(err)) } finally { setOcupado(false) }
  }

  return <main className="min-h-screen bg-[#f6f5f0] px-5 py-12 text-slate-900">
    <div className="mx-auto max-w-3xl rounded-xl border border-[#dce3dc] bg-white p-7 shadow-sm sm:p-10">
      <Link to="/" className="text-sm font-semibold text-brand-700">← Volver al inicio</Link>
      <p className="mt-8 text-xs font-bold uppercase tracking-[0.15em] text-brand-700">Un espacio para tu comunidad</p>
      <h1 className="mt-3 font-serif text-4xl text-[#172a25]">Registra tu colegio</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">Cuéntanos sobre tu institución y la persona responsable. El responsable será el administrador director y podrá iniciar sesión al terminar el registro.</p>
      {registro ? <div className="mt-6 space-y-3 rounded-xl bg-brand-50 p-5">
        <p>Cuenta creada correctamente. Puedes iniciar sesión con el usuario o correo y la contraseña que registraste.</p>
        {registro.modo_correo === 'consola' && <p className="text-sm">El correo de verificación se imprimió en la consola de desarrollo.</p>}
        {registro.modo_correo === 'no_disponible' && <p className="text-sm">La verificación por correo quedó pendiente.</p>}
        {checkout && <a className="inline-block rounded-xl bg-brand-700 px-5 py-3 font-semibold text-white" href={checkout}>Pagar con Stripe</a>}
        {registro.checkout_pendiente && <p className="text-sm">Puedes reintentar el pago desde Suscripciones después de iniciar sesión.</p>}
        {registro.qr_simulado_pendiente && <p className="text-sm">Inicia sesión, abre Suscripciones y elige «Pagar con QR simulado» para activar el plan.</p>}
        <Link className="block font-semibold text-brand-700" to="/login">Ir a iniciar sesión</Link>
      </div> :
        <form onSubmit={(e) => void enviar(e)} className="mt-6 space-y-6">
          <div className="border-t border-slate-200 pt-6"><h2 className="mb-1 text-lg font-semibold">Responsable de la institución</h2><p className="mb-4 text-sm text-slate-500">Datos de la persona que administrará la cuenta.</p><div className="grid gap-4 sm:grid-cols-2">
            <Campo nombre="nombre" etiqueta="Nombre" /><Campo nombre="apellido" etiqueta="Apellido" />
            <Campo nombre="username" etiqueta="Usuario de acceso" placeholder="director.colegio" /><Campo nombre="email" etiqueta="Correo de acceso" type="email" />
            <Campo nombre="telefono_responsable" etiqueta="Teléfono del responsable" placeholder="+59170000000" /><Campo nombre="password" etiqueta="Contraseña" type="password" />
          </div></div>
          <div className="border-t border-slate-200 pt-6"><h2 className="mb-1 text-lg font-semibold">Datos del colegio</h2><p className="mb-4 text-sm text-slate-500">Ubicación y datos de contacto institucional.</p><div className="grid gap-4 sm:grid-cols-2">
            <Campo nombre="colegio" etiqueta="Nombre del colegio" />
            <label className="text-sm font-medium">País<select className={inputClass} name="pais" required defaultValue="BO"><option value="BO">Bolivia</option><option value="US">Estados Unidos</option><option value="AR">Argentina</option><option value="BR">Brasil</option><option value="CL">Chile</option><option value="CO">Colombia</option><option value="ES">España</option><option value="MX">México</option><option value="PE">Perú</option></select></label>
            <Campo nombre="region" etiqueta="Estado, departamento o región" /><Campo nombre="ciudad" etiqueta="Ciudad" />
            <Campo nombre="direccion" etiqueta="Dirección" /><Campo nombre="telefono" etiqueta="Teléfono internacional" placeholder="+59170000000" />
            <label className="text-sm font-medium">Zona horaria<input className={inputClass} name="zona_horaria" defaultValue={Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/La_Paz'} required /></label>
            <label className="text-sm font-medium">Idioma<select className={inputClass} name="idioma"><option value="es">Español</option><option value="en">English</option></select></label>
          </div></div>
          <div className="border-t border-slate-200 pt-6"><h2 className="mb-1 text-lg font-semibold">Facturación</h2><p className="mb-4 text-sm text-slate-500">Información para la contratación de tu plan.</p><div className="grid gap-4 sm:grid-cols-2">
            <Campo nombre="razon_facturacion" etiqueta="Nombre o razón de facturación" /><Campo nombre="email_facturacion" etiqueta="Correo de facturación" type="email" />
            <Campo nombre="identificacion_fiscal" etiqueta="Identificación fiscal (opcional)" required={false} />
          </div></div>
          <div className="grid gap-4 border-t border-slate-200 pt-6 sm:grid-cols-2">
            <div>
              <label htmlFor="plan-registro" className="text-sm font-medium">Plan de suscripción</label>
              <select id="plan-registro" className={inputClass} disabled={planes === null}
                value={planSeleccionado?.id ?? ''} onChange={(e) => setPlanElegido(e.target.value)}>
                <option value="">{planes === null ? 'Cargando planes…' : 'Elegir el plan más adelante'}</option>
                {planes?.map((item) => <option key={item.id} value={item.id}>
                  {item.nombre} · {item.precio} {item.moneda} / {item.periodicidad_display.toLowerCase()}
                </option>)}
              </select>
            </div>
            <div>
              <label htmlFor="metodo-pago-registro" className="text-sm font-medium">Método de pago</label>
              <select id="metodo-pago-registro" className={inputClass} disabled={!requierePago || !metodosDisponibles.length}
                value={requierePago ? metodoPago : ''} onChange={(e) => setMetodoElegido(e.target.value)}>
                {!requierePago && <option value="">{planSeleccionado ? 'Plan sin costo' : 'Selecciona un plan para pagar'}</option>}
                {requierePago && !metodosDisponibles.length && <option value="">Métodos no disponibles</option>}
                {requierePago && metodosDisponibles.map((metodo) => <option key={metodo.codigo} value={metodo.codigo}>
                  {metodo.nombre}{metodo.codigo === 'STRIPE' && metodo.modo_prueba ? ' (modo prueba)' : ''}
                </option>)}
              </select>
              {requierePago && metodoPago === 'STRIPE' && <p className="mt-2 text-sm text-slate-500">Completa el pago en la página de Stripe después de crear la cuenta.</p>}
              {requierePago && metodoPago === 'QR_SIMULADO' && <p className="mt-2 text-sm text-slate-500">Podrás confirmar el pago de demostración en Suscripciones después de iniciar sesión.</p>}
            </div>
          </div>
          <label className="flex gap-2 text-sm"><input name="acepta_condiciones" type="checkbox" required /> Confirmo que tengo autorización para registrar esta institución y acepto que el acceso académico requiere una suscripción contratada.</label>
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <button disabled={ocupado || planes === null} className="rounded-xl bg-brand-700 px-5 py-3 font-semibold text-white disabled:opacity-50">{ocupado ? 'Registrando...' : 'Crear cuenta'}</button>
        </form>}
    </div>
  </main>
}

export function VerificarCorreo() {
  const [params] = useSearchParams()
  const [estado, setEstado] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [email, setEmail] = useState('')
  async function verificar() {
    setOcupado(true)
    try { const result = await authAxios.post<{ detail: string; plan: number | null }>('/usuarios/verificar-correo/', { token: params.get('token') }); if (result.data.plan) localStorage.setItem('plan_seleccionado', String(result.data.plan)); setEstado(result.data.detail) }
    catch (err) { setEstado(mensaje(err)) } finally { setOcupado(false) }
  }
  async function reenviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setOcupado(true)
    try { const result = await authAxios.post<{ detail: string }>('/usuarios/reenviar-verificacion/', { email }); setEstado(result.data.detail) }
    catch (err) { setEstado(mensaje(err)) } finally { setOcupado(false) }
  }
  return <main className="min-h-screen bg-[#f6f5f0] p-8"><div className="mx-auto max-w-lg rounded-xl border border-[#dce3dc] bg-white p-8 shadow-sm">
    <p className="mb-3 text-xs font-bold uppercase tracking-[0.15em] text-brand-700">Tu cuenta institucional</p><h1 className="font-serif text-3xl">Verificar correo</h1>
    <p className="mt-4">Confirma que esta dirección corresponde a tu cuenta institucional.</p>
    {estado && <p role="status" className="mt-4">{estado}</p>}
    {!estado && <button disabled={ocupado || !params.get('token')} onClick={() => void verificar()} className="mt-5 rounded-xl bg-brand-700 px-5 py-3 font-semibold text-white">{ocupado ? 'Verificando...' : 'Confirmar correo'}</button>}
    <form onSubmit={(event) => void reenviar(event)} className="mt-6 border-t pt-4">
      <label className="text-sm font-medium">¿Necesitas otro enlace?<input className={inputClass} type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Correo de registro" required /></label>
      <button disabled={ocupado} className="mt-3 text-sm font-semibold text-brand-700">Reenviar enlace</button>
    </form>
    <Link to="/login" className="mt-5 block font-semibold text-brand-700">Ir a iniciar sesión</Link>
  </div></main>
}

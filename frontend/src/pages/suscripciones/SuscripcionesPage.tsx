import axios from 'axios'
import { AlertTriangle, CreditCard, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import {
  cancelarSuscripcion, contratarPlan, crearPlan, editarPlan, eliminarPlan,
  crearMetodoPago, editarMetodoPago, listarMetodosPago, listarMetodosPagoPublicos,
  generarQr, generarQrSimulado, consultarQr, simularPagoQr, iniciarCheckoutStripe, urlCheckoutStripe,
  listarColegiosCatalogo, listarPagos, listarPlanes, listarSuscripciones,
  normalizarPagos, normalizarPlanes, normalizarSuscripciones, obtenerEstadoSuscripcion,
  rechazarPago, reactivarSuscripcion, registrarPago, suspenderSuscripcion, validarPago,
  type ColegioCatalogo, type EstadoSuscripcion, type MetodoPago, type Pago, type Plan,
  type PlanPayload, type Suscripcion,
} from '../../api/suscripciones'

const PERIODICIDADES = [
  ['MENSUAL', 'Mensual'], ['TRIMESTRAL', 'Trimestral'],
  ['SEMESTRAL', 'Semestral'], ['ANUAL', 'Anual'],
]

const planInicial = {
  nombre: '', descripcion: '', precio: '', moneda: 'BOB', periodicidad: 'MENSUAL',
  modulos_habilitados: '', limite_usuarios: '0', limite_unidades: '0', estado: 'ACTIVO',
}

const pagoInicial = { suscripcion: '', metodo: 'TRANSFERENCIA', referencia: '', monto: '', observacion: '' }
const metodoInicial = { codigo: 'TRANSFERENCIA', nombre: '', descripcion: '', activo: true }
const metodosEnLinea = ['PASARELA', 'STRIPE', 'QR_SIMULADO']

const contratacionInicial = { plan: '', colegio: '', fecha_inicio: '' }

const coloresEstado: Record<string, string> = {
  ACTIVA: 'bg-emerald-50 text-emerald-700',
  PENDIENTE: 'bg-amber-50 text-amber-700',
  VENCIDA: 'bg-red-50 text-red-700',
  SUSPENDIDA: 'bg-orange-50 text-orange-700',
  CANCELADA: 'bg-slate-100 text-slate-600',
}

export default function SuscripcionesPage() {
  const { can, isSuperAdmin } = useAuth()
  const esPlataforma = isSuperAdmin()
  const puedeContratar = esPlataforma || can('suscripcion', 'crear')
  const puedeVerPagos = esPlataforma || can('pago', 'listar')

  const [tab, setTab] = useState<'suscripciones' | 'pagos' | 'planes' | 'metodos'>('suscripciones')
  const [estadoColegio, setEstadoColegio] = useState<EstadoSuscripcion | null>(null)
  const [suscripciones, setSuscripciones] = useState<Suscripcion[]>([])
  const [pagos, setPagos] = useState<Pago[]>([])
  const [planes, setPlanes] = useState<Plan[]>([])
  const [metodos, setMetodos] = useState<MetodoPago[]>([])
  const [colegios, setColegios] = useState<ColegioCatalogo[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')

  const [modalContratar, setModalContratar] = useState(false)
  const [formContratar, setFormContratar] = useState(contratacionInicial)
  const [modalPago, setModalPago] = useState(false)
  const [formPago, setFormPago] = useState(pagoInicial)
  const [modalPlan, setModalPlan] = useState(false)
  const [modalMetodo, setModalMetodo] = useState(false)
  const [editandoMetodo, setEditandoMetodo] = useState<MetodoPago | null>(null)
  const [formMetodo, setFormMetodo] = useState(metodoInicial)
  const [editandoPlan, setEditandoPlan] = useState<Plan | null>(null)
  const [formPlan, setFormPlan] = useState(planInicial)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [enviando, setEnviando] = useState(false)
  const [pagoQr, setPagoQr] = useState<Pago | null>(null)
  const metodoStripe = metodos.find((metodo) => metodo.codigo === 'STRIPE' && metodo.activo && metodo.disponible !== false)
  const metodoVendis = metodos.find((metodo) => metodo.codigo === 'PASARELA' && metodo.activo && metodo.disponible === true)
  const metodoQrSimulado = metodos.find((metodo) => metodo.codigo === 'QR_SIMULADO' && metodo.activo && metodo.disponible === true)
  const esQrSimulado = pagoQr?.metodo === 'QR_SIMULADO'
  const imagenQr = esQrSimulado ? pagoQr?.qr_imagen_simulada : pagoQr?.qr_url
  const retornoStripe = new URLSearchParams(window.location.search).get('stripe')
  const suscripcionesPagables = suscripciones.filter((suscripcion) => Number(suscripcion.precio_periodico) > 0)

  const cargar = useCallback(async () => {
    setCargando(true); setError('')
    try {
      const tareas: Promise<unknown>[] = [listarSuscripciones().then((r) => setSuscripciones(normalizarSuscripciones(r.data)))]
      tareas.push(listarPlanes().then((r) => setPlanes(normalizarPlanes(r.data))))
      if (!esPlataforma) tareas.push(obtenerEstadoSuscripcion().then((r) => setEstadoColegio(r.data)))
      if (puedeVerPagos) tareas.push(listarPagos().then((r) => setPagos(normalizarPagos(r.data))))
      tareas.push((esPlataforma ? listarMetodosPago() : listarMetodosPagoPublicos()).then(({ data }) => setMetodos(data)))
      if (esPlataforma) {
        tareas.push(listarColegiosCatalogo().then(setColegios))
      }
      await Promise.all(tareas)
    }
    catch (e) {
      const s = axios.isAxiosError(e) ? e.response?.status : undefined
      setError(s === 403
        ? 'Su suscripción no está activa. Solo puede consultar el estado de su suscripción y registrar pagos de renovación.'
        : s === 400
          ? 'No se pudo consultar el estado de la suscripción.'
          : 'No fue posible cargar la información de suscripciones.')
    }
    finally { setCargando(false) }
  }, [esPlataforma, puedeVerPagos])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar() }, [cargar])

  const abrirContratar = () => {
    setErrores({}); setError('')
    setFormContratar({ ...contratacionInicial, plan: localStorage.getItem('plan_seleccionado') ?? '' })
    setModalContratar(true)
  }

  const guardarContratacion = async () => {
    if (enviando) return
    const e: Record<string, string> = {}
    if (!formContratar.plan) e.plan = 'Seleccione un plan.'
    if (esPlataforma && !formContratar.colegio) e.colegio = 'Seleccione el colegio que contrata.'
    setErrores(e)
    if (Object.keys(e).length) return
    setEnviando(true); setError('')
    try {
      const payload: { plan: number; colegio?: number; fecha_inicio?: string } = {
        plan: Number(formContratar.plan),
      }
      if (esPlataforma) payload.colegio = Number(formContratar.colegio)
      if (formContratar.fecha_inicio) payload.fecha_inicio = formContratar.fecha_inicio
      await contratarPlan(payload)
      localStorage.removeItem('plan_seleccionado')
      setModalContratar(false)
      setExito('Plan contratado. La suscripción queda pendiente de validación del pago.')
      await cargar()
    }
    catch (err) {
      const respuesta = axios.isAxiosError(err) ? err.response : undefined
      const s = respuesta?.status
      setError(s === 403 ? 'No tiene permiso para contratar planes.'
        : s === 400 ? mensajeDominio(respuesta?.data)
          : 'No fue posible contratar el plan.')
    }
    finally { setEnviando(false) }
  }

  const transicion = async (
    suscripcion: Suscripcion, accion: 'suspender' | 'cancelar' | 'reactivar',
  ) => {
    const textos = { suspender: 'suspender', cancelar: 'cancelar', reactivar: 'reactivar' }
    if (!window.confirm(`¿${textos[accion][0].toUpperCase()}${textos[accion].slice(1)} la suscripción de ${suscripcion.colegio_nombre}?`)) return
    try {
      if (accion === 'suspender') await suspenderSuscripcion(suscripcion.id)
      else if (accion === 'cancelar') await cancelarSuscripcion(suscripcion.id)
      else await reactivarSuscripcion(suscripcion.id)
      setExito(`Suscripción ${accion === 'suspender' ? 'suspendida' : accion === 'cancelar' ? 'cancelada' : 'reactivada'}.`)
      await cargar()
    }
    catch { setError('No fue posible cambiar el estado de la suscripción.') }
  }

  const abrirPago = () => {
    setErrores({}); setError(''); setFormPago(pagoInicial); setModalPago(true)
  }

  const iniciarQr = async (id: number, simulado = false) => {
    if (enviando) return
    setEnviando(true); setError('')
    try {
      const { data } = await (simulado ? generarQrSimulado(id) : generarQr(id))
      setPagoQr(data)
      await cargar()
    }
    catch (err) {
      const respuesta = axios.isAxiosError(err) ? err.response : undefined
      setError(respuesta?.data ? mensajeDominio(respuesta.data) : 'No se pudo confirmar la generación. Consulta los pagos pendientes antes de volver a intentarlo.')
    } finally { setEnviando(false) }
  }

  const iniciarStripe = async (id: number) => {
    if (enviando) return
    setEnviando(true); setError('')
    try {
      const { data } = await iniciarCheckoutStripe(id)
      const destino = urlCheckoutStripe(data.checkout_url)
      if (!destino) throw new Error('Checkout inválido')
      window.location.assign(destino)
    } catch (err) {
      const respuesta = axios.isAxiosError(err) ? err.response : undefined
      setError(respuesta?.data ? mensajeDominio(respuesta.data) : 'No fue posible abrir Stripe.')
    } finally {
      setEnviando(false)
    }
  }

  const verificarQr = async (pago: Pago) => {
    if (enviando) return
    setEnviando(true); setError('')
    try {
      const simulado = pago.metodo === 'QR_SIMULADO'
      const respuesta = await (simulado ? simularPagoQr(pago.id) : consultarQr(pago.id))
      setPagoQr(respuesta.data)
      if (respuesta.data.resultado === 'VALIDADO') {
        setExito(simulado ? 'Pago simulado confirmado. Suscripción activa.' : 'Pago confirmado y suscripción activada.')
      }
      await cargar()
    } catch (err) {
      const respuesta = axios.isAxiosError(err) ? err.response : undefined
      setError(respuesta?.data ? mensajeDominio(respuesta.data) : 'No fue posible consultar el pago.')
    } finally { setEnviando(false) }
  }

  const guardarPago = async () => {
    if (enviando) return
    const e: Record<string, string> = {}
    if (!formPago.suscripcion) e.suscripcion = 'Seleccione la suscripción.'
    if (!formPago.referencia.trim()) e.referencia = 'Indique la referencia del pago.'
    if (!formPago.monto || Number(formPago.monto) <= 0) e.monto = 'El monto debe ser mayor a cero.'
    setErrores(e)
    if (Object.keys(e).length) return
    setEnviando(true); setError('')
    try {
      await registrarPago({
        suscripcion: Number(formPago.suscripcion),
        metodo: formPago.metodo,
        referencia: formPago.referencia.trim(),
        monto: formPago.monto,
        observacion: formPago.observacion.trim() || undefined,
      })
      setModalPago(false)
      setExito('Pago registrado. Queda pendiente de validación por la plataforma.')
      await cargar()
    }
    catch (err) {
      const respuesta = axios.isAxiosError(err) ? err.response : undefined
      setError(respuesta?.status === 400 ? mensajeDominio(respuesta?.data) : 'No fue posible registrar el pago.')
    }
    finally { setEnviando(false) }
  }

  const accionPago = async (pago: Pago, accion: 'validar' | 'rechazar') => {
    if (accion === 'rechazar' && !window.confirm(`¿Rechazar el pago ${pago.id}?`)) return
    try {
      if (accion === 'validar') { await validarPago(pago.id); setExito(`Pago ${pago.id} validado.`) }
      else {
        const motivo = window.prompt('Motivo del rechazo:', 'Comprobante ilegible')
        if (motivo === null) return
        await rechazarPago(pago.id, motivo.trim() || 'Sin motivo informado')
        setExito(`Pago ${pago.id} rechazado.`)
      }
      await cargar()
    }
    catch { setError(`No fue posible ${accion} el pago.`) }
  }

  const abrirPlan = (plan?: Plan) => {
    setEditandoPlan(plan ?? null); setErrores({}); setError('')
    setFormPlan(plan
      ? {
          nombre: plan.nombre, descripcion: plan.descripcion, precio: plan.precio, moneda: plan.moneda,
          periodicidad: plan.periodicidad,
          modulos_habilitados: plan.modulos_habilitados.join(', '),
          limite_usuarios: String(plan.limite_usuarios),
          limite_unidades: String(plan.limite_unidades), estado: plan.estado,
        }
      : planInicial)
    setModalPlan(true)
  }

  const guardarPlan = async () => {
    if (enviando) return
    const e: Record<string, string> = {}
    if (!formPlan.nombre.trim()) e.nombre = 'Indique el nombre del plan.'
    if (!formPlan.precio || Number(formPlan.precio) < 0) e.precio = 'Indique un precio válido.'
    setErrores(e)
    if (Object.keys(e).length) return
    setEnviando(true); setError('')
    const payload: PlanPayload = {
      nombre: formPlan.nombre.trim(),
      descripcion: formPlan.descripcion.trim(),
      precio: formPlan.precio,
      moneda: formPlan.moneda,
      periodicidad: formPlan.periodicidad,
      modulos_habilitados: formPlan.modulos_habilitados
        .split(',').map((m) => m.trim()).filter(Boolean),
      limite_usuarios: Number(formPlan.limite_usuarios) || 0,
      limite_unidades: Number(formPlan.limite_unidades) || 0,
      estado: formPlan.estado,
    }
    try {
      if (editandoPlan) await editarPlan(editandoPlan.id, payload)
      else await crearPlan(payload)
      setModalPlan(false)
      setExito(editandoPlan ? 'Plan actualizado. Las suscripciones contratadas conservan su snapshot.' : 'Plan creado.')
      await cargar()
    }
    catch (err) {
      const respuesta = axios.isAxiosError(err) ? err.response : undefined
      setError(respuesta?.status === 400 ? mensajeDominio(respuesta?.data) : 'No fue posible guardar el plan.')
    }
    finally { setEnviando(false) }
  }

  const borrarPlan = async (plan: Plan) => {
    if (!window.confirm(`¿Dar de baja el plan ${plan.nombre}? El historial de suscripciones se conserva.`)) return
    try { await eliminarPlan(plan.id); setExito('Plan dado de baja.'); await cargar() }
    catch { setError('No fue posible dar de baja el plan.') }
  }

  const abrirMetodo = (metodo?: MetodoPago) => {
    setEditandoMetodo(metodo ?? null); setErrores({}); setError('')
    setFormMetodo(metodo ? { codigo: metodo.codigo, nombre: metodo.nombre, descripcion: metodo.descripcion, activo: metodo.activo } : metodoInicial)
    setModalMetodo(true)
  }

  const guardarMetodo = async () => {
    if (!formMetodo.nombre.trim()) { setErrores({ nombre_metodo: 'Indique el nombre visible.' }); return }
    setEnviando(true); setError('')
    try {
      if (editandoMetodo) await editarMetodoPago(editandoMetodo.id, { nombre: formMetodo.nombre.trim(), descripcion: formMetodo.descripcion.trim(), activo: formMetodo.activo })
      else await crearMetodoPago({ ...formMetodo, codigo: formMetodo.codigo as MetodoPago['codigo'], nombre: formMetodo.nombre.trim(), descripcion: formMetodo.descripcion.trim() })
      setModalMetodo(false); setExito(editandoMetodo ? 'Método de pago actualizado.' : 'Método de pago configurado.')
      await cargar()
    } catch (err) { const respuesta = axios.isAxiosError(err) ? err.response : undefined; setError(respuesta?.status === 400 ? mensajeDominio(respuesta.data) : 'No fue posible guardar el método de pago.') }
    finally { setEnviando(false) }
  }

  const tabs: Array<{ clave: typeof tab; etiqueta: string }> = [
    { clave: 'suscripciones', etiqueta: 'Suscripciones' },
    ...(puedeVerPagos ? [{ clave: 'pagos' as const, etiqueta: 'Pagos' }] : []),
    ...(esPlataforma ? [{ clave: 'metodos' as const, etiqueta: 'Métodos de pago' }] : []),
    ...(esPlataforma ? [{ clave: 'planes' as const, etiqueta: 'Planes' }] : []),
  ]

  return (
    <section className="p-4 sm:p-6 lg:p-8" aria-labelledby="suscripciones-titulo">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <CreditCard className="text-brand-700" />
            <h1 id="suscripciones-titulo" className="text-2xl font-bold">Suscripciones SaaS</h1>
          </div>
          <p className="mt-1 text-sm text-slate-500">Planes, contrataciones, pagos y límites del colegio.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => void cargar()} aria-label="Actualizar suscripciones">
            <RefreshCw size={17} />Actualizar
          </button>
          {puedeContratar && <button className="btn-primary" onClick={abrirContratar}><Plus size={18} />Contratar plan</button>}
        </div>
      </header>

      {!esPlataforma && estadoColegio && (
        <div
          role="status"
          className={`mb-5 rounded-2xl border p-4 text-sm ${
            estadoColegio.restriccion
              ? 'border-amber-200 bg-amber-50 text-amber-800'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800'
          }`}
        >
          <p className="font-semibold">
            {estadoColegio.tiene_suscripcion
              ? `${estadoColegio.plan} — ${estadoColegio.estado_display}`
              : 'Sin suscripción contratada (modo prototipo).'}
            {estadoColegio.fecha_vencimiento && ` · Vence el ${estadoColegio.fecha_vencimiento}`}
            {estadoColegio.precio_periodico && ` · ${estadoColegio.precio_periodico} ${estadoColegio.moneda ?? 'BOB'} / ${estadoColegio.periodicidad_display?.toLowerCase() ?? 'periodo'}`}
          </p>
          {estadoColegio.restriccion && <p className="mt-1">{estadoColegio.restriccion}</p>}
          <p className="mt-1 text-xs">
            Límites: {estadoColegio.limite_usuarios ? `${estadoColegio.limite_usuarios} usuarios` : 'usuarios sin límite'}
            {' · '}
            {estadoColegio.limite_unidades ? `${estadoColegio.limite_unidades} unidades` : 'unidades sin límite'}
          </p>
        </div>
      )}

      <nav className="mb-5 flex gap-2" aria-label="Secciones de suscripciones">
        {tabs.map((t) => (
          <button
            key={t.clave}
            type="button"
            onClick={() => setTab(t.clave)}
            aria-current={tab === t.clave ? 'page' : undefined}
            className={tab === t.clave ? 'btn-primary' : 'btn-secondary'}
          >
            {t.etiqueta}
          </button>
        ))}
      </nav>

      {exito && <p role="status" className="mb-4 rounded-xl bg-emerald-50 p-3 text-emerald-700">{exito}</p>}
      {error && !pagoQr && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}
      {retornoStripe === 'confirmacion' && <p role="status" className="mb-4 rounded-xl bg-blue-50 p-3 text-blue-800">La suscripción se actualizará cuando Stripe confirme el pago.</p>}
      {retornoStripe === 'cancelado' && <p role="status" className="mb-4 rounded-xl bg-amber-50 p-3 text-amber-800">Puedes volver a abrir el pago desde tu suscripción.</p>}

      {cargando && <p className="p-8 text-center text-slate-500">Cargando información...</p>}

      {!cargando && tab === 'suscripciones' && (
        <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
          {suscripciones.length === 0
            ? <p className="p-8 text-center text-slate-500">No hay suscripciones registradas.</p>
            : (
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    {['Colegio', 'Plan', 'Precio', 'Vigencia', 'Módulos', 'Estado', 'Estado efectivo', 'Acciones']
                      .map((x) => <th key={x} className="px-4 py-3">{x}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {suscripciones.map((s) => (
                    <tr key={s.id} className="border-t border-slate-100">
                      <td className="px-4 py-3">{s.colegio_nombre}</td>
                      <td className="px-4 py-3">{s.plan_nombre}</td>
                      <td className="whitespace-nowrap px-4 py-3">{s.precio_periodico} {s.moneda} / {s.periodicidad_display.toLowerCase()}</td>
                      <td className="whitespace-nowrap px-4 py-3">{s.fecha_inicio} – {s.fecha_vencimiento}</td>
                      <td className="px-4 py-3">{s.modulos_habilitados.length ? s.modulos_habilitados.join(', ') : 'Todos'}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2 py-1 text-xs font-medium ${coloresEstado[s.estado] ?? 'bg-slate-100 text-slate-600'}`}>
                          {s.estado_display}
                        </span>
                      </td>
                      <td className="px-4 py-3">{s.estado_efectivo}</td>
                      <td className="px-4 py-3">
                        {puedeContratar && metodoQrSimulado && s.qr_simulado_disponible && ['PENDIENTE', 'VENCIDA'].includes(s.estado_efectivo) && (
                          <button disabled={enviando} className="mr-3 text-brand-700" onClick={() => void iniciarQr(s.id, true)}>Pagar con QR simulado</button>
                        )}
                        {puedeContratar && metodoVendis && s.moneda === 'BOB' && Number(s.precio_periodico) > 0 && ['PENDIENTE', 'VENCIDA'].includes(s.estado_efectivo) && (
                          <button disabled={enviando} className="mr-3 text-brand-700" onClick={() => void iniciarQr(s.id)}>Pagar con QR</button>
                        )}
                        {puedeContratar && metodoStripe && Number(s.precio_periodico) > 0 && ['PENDIENTE', 'VENCIDA'].includes(s.estado_efectivo) && (
                          <button disabled={enviando} className="mr-3 text-brand-700" onClick={() => void iniciarStripe(s.id)}>
                            Pagar con Stripe{metodoStripe.modo_prueba ? ' (modo prueba)' : ''}
                          </button>
                        )}
                        {esPlataforma && (
                          <div className="flex gap-2">
                            {(s.estado === 'ACTIVA' || s.estado === 'PENDIENTE') && (
                              <button className="text-amber-700" aria-label={`Suspender suscripción ${s.id}`} onClick={() => void transicion(s, 'suspender')}>
                                Suspender
                              </button>
                            )}
                            {s.estado !== 'CANCELADA' && (
                              <button className="text-red-600" aria-label={`Cancelar suscripción ${s.id}`} onClick={() => void transicion(s, 'cancelar')}>
                                Cancelar
                              </button>
                            )}
                            {s.estado === 'SUSPENDIDA' && (
                              <button className="text-emerald-700" aria-label={`Reactivar suscripción ${s.id}`} onClick={() => void transicion(s, 'reactivar')}>
                                Reactivar
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </div>
      )}

      {!cargando && tab === 'pagos' && (
        <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
          <div className="flex flex-wrap justify-end gap-2 p-3">
            {esPlataforma && <button className="btn-secondary" onClick={() => setTab('metodos')}>Configurar métodos de pago</button>}
            {suscripcionesPagables.length > 0
              ? <button className="btn-primary" onClick={abrirPago}><Plus size={17} />Registrar pago</button>
              : <p className="self-center text-sm text-slate-500">No hay suscripciones de pago.</p>}
          </div>
          {pagos.length === 0
            ? <p className="p-8 text-center text-slate-500">No hay pagos registrados.</p>
            : (
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    {['N°', 'Colegio', 'Plan', 'Método', 'Referencia', 'Monto', 'Fecha', 'Resultado', 'Acciones']
                      .map((x) => <th key={x} className="px-4 py-3">{x}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {pagos.map((p) => (
                    <tr key={p.id} className="border-t border-slate-100">
                      <td className="px-4 py-3">{p.id}</td>
                      <td className="px-4 py-3">{p.suscripcion_colegio_nombre}</td>
                      <td className="px-4 py-3">{p.suscripcion_plan_nombre}</td>
                      <td className="px-4 py-3">{p.metodo_display}</td>
                      <td className="px-4 py-3">{p.referencia}</td>
                      <td className="whitespace-nowrap px-4 py-3">{p.monto} {p.moneda}</td>
                      <td className="px-4 py-3">{p.fecha}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                          p.resultado === 'VALIDADO' ? 'bg-emerald-50 text-emerald-700'
                            : p.resultado === 'RECHAZADO' ? 'bg-red-50 text-red-700'
                              : 'bg-amber-50 text-amber-700'
                        }`}>
                          {p.resultado_display}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {p.metodo === 'PASARELA' && p.qr_url && p.resultado === 'PENDIENTE' && (
                          <button className="mr-3 text-brand-700" onClick={() => setPagoQr(p)}>Ver QR</button>
                        )}
                        {esPlataforma && !metodosEnLinea.includes(p.metodo) && p.resultado === 'PENDIENTE' && (
                          <div className="flex gap-2">
                            <button className="text-emerald-700" aria-label={`Validar pago ${p.id}`} onClick={() => void accionPago(p, 'validar')}>Validar</button>
                            <button className="text-red-600" aria-label={`Rechazar pago ${p.id}`} onClick={() => void accionPago(p, 'rechazar')}>Rechazar</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </div>
      )}

      {!cargando && tab === 'planes' && esPlataforma && (
        <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
          <div className="flex justify-end p-3">
            <button className="btn-primary" onClick={() => abrirPlan()}><Plus size={17} />Nuevo plan</button>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50">
              <tr>
                {['Plan', 'Precio', 'Periodicidad', 'Límite usuarios', 'Límite unidades', 'Módulos', 'Estado', 'Acciones']
                  .map((x) => <th key={x} className="px-4 py-3">{x}</th>)}
              </tr>
            </thead>
            <tbody>
              {planes.map((p) => (
                <tr key={p.id} className="border-t border-slate-100">
                  <td className="px-4 py-3">{p.nombre}</td>
                  <td className="px-4 py-3">{p.precio} {p.moneda}</td>
                  <td className="px-4 py-3">{p.periodicidad_display}</td>
                  <td className="px-4 py-3">{p.limite_usuarios || 'Sin límite'}</td>
                  <td className="px-4 py-3">{p.limite_unidades || 'Sin límite'}</td>
                  <td className="px-4 py-3">{p.modulos_habilitados.length ? p.modulos_habilitados.join(', ') : 'Todos'}</td>
                  <td className="px-4 py-3">{p.estado_display}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button aria-label={`Editar plan ${p.id}`} className="text-brand-700" onClick={() => abrirPlan(p)}><Pencil size={17} /></button>
                      <button aria-label={`Eliminar plan ${p.id}`} className="text-red-600" onClick={() => void borrarPlan(p)}><Trash2 size={17} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!cargando && tab === 'metodos' && esPlataforma && (
        <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
          <div className="flex items-center justify-between p-3"><p className="text-sm text-slate-500">Los métodos activos se muestran durante el registro institucional y al registrar pagos.</p><button className="btn-primary" onClick={() => abrirMetodo()}><Plus size={17} />Configurar método</button></div>
          <table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr>{['Código', 'Nombre visible', 'Descripción', 'Estado', 'Acciones'].map((x) => <th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{metodos.map((metodo) => <tr key={metodo.id} className="border-t border-slate-100"><td className="px-4 py-3">{metodo.codigo}</td><td className="px-4 py-3">{metodo.nombre}</td><td className="px-4 py-3">{metodo.descripcion || '—'}</td><td className="px-4 py-3">{metodo.activo ? 'Activo' : 'Inactivo'}</td><td className="px-4 py-3"><button className="text-brand-700" aria-label={`Editar método ${metodo.id}`} onClick={() => abrirMetodo(metodo)}><Pencil size={17}/></button></td></tr>)}</tbody></table>
        </div>
      )}

      {modalContratar && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6">
            <button aria-label="Cerrar formulario" className="float-right" onClick={() => setModalContratar(false)}><X /></button>
            <h2 className="text-xl font-bold">Contratar plan</h2>
            <p className="mt-1 text-sm text-slate-500">La suscripción nace pendiente de pago; un pago validado la activa.</p>
            <div className="mt-5 grid gap-4">
              {esPlataforma && (
                <Select label="Colegio" value={formContratar.colegio} error={errores.colegio}
                  onChange={(v) => setFormContratar({ ...formContratar, colegio: v })}
                  opciones={[['', 'Seleccione'], ...colegios.map((c) => [String(c.id), c.nombre])]} />
              )}
              <Select label="Plan" value={formContratar.plan} error={errores.plan}
                onChange={(v) => setFormContratar({ ...formContratar, plan: v })}
                opciones={[['', 'Seleccione'], ...planes.filter((p) => p.estado === 'ACTIVO').map((p) => [String(p.id), `${p.nombre} — ${p.precio} ${p.moneda} / ${p.periodicidad_display.toLowerCase()}`])]} />
              {planes.filter((p) => String(p.id) === formContratar.plan && p.estado === 'ACTIVO').map((p) => (
                <div key={p.id} className="rounded-xl bg-brand-50 p-4 text-sm text-slate-700">
                  <p className="font-semibold">Resumen: {p.nombre} · {p.precio} {p.moneda} / {p.periodicidad_display.toLowerCase()}</p>
                  <p className="mt-2">Usuarios: {p.limite_usuarios || 'Sin límite'} · Unidades: {p.limite_unidades || 'Sin límite'}</p>
                  <p className="mt-1">Módulos: {p.modulos_habilitados.length ? p.modulos_habilitados.join(', ') : 'Todos'}</p>
                  <p className="mt-1">Renovación manual. El acceso requiere un pago validado y que haya llegado la fecha de inicio.</p>
                  {p.moneda !== 'BOB' && <p className="mt-1">El QR está disponible solo en BOB. Coordina el pago internacional con la plataforma.</p>}
                </div>
              ))}
              <Campo label="Fecha de inicio (opcional)" type="date" value={formContratar.fecha_inicio}
                error={errores.fecha_inicio}
                onChange={(v) => setFormContratar({ ...formContratar, fecha_inicio: v })} />
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button className="btn-secondary" onClick={() => setModalContratar(false)}>Cancelar</button>
              <button className="btn-primary" disabled={enviando} onClick={() => void guardarContratacion()}>
                {enviando ? 'Contratando...' : 'Contratar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {pagoQr && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true" aria-label="Pago QR">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 text-center">
            <button aria-label="Cerrar QR" className="float-right" onClick={() => { setPagoQr(null); setError('') }} disabled={enviando}><X /></button>
            <h2 className="text-xl font-bold">{esQrSimulado ? 'QR simulado' : 'Pago de suscripción'}</h2>
            <p className="mt-2">{pagoQr.suscripcion_colegio_nombre} · {pagoQr.monto} {pagoQr.moneda}</p>
            {esQrSimulado && <p className="mt-2 text-sm text-slate-600">Código de demostración. Confirma con el botón de abajo para probar el pago.</p>}
            {esQrSimulado && metodoStripe?.modo_prueba && pagoQr.resultado === 'PENDIENTE' && (
              <p className="mt-2 text-sm text-slate-600">Si abriste un pago de prueba en Stripe, se cerrará al simular el pago.</p>
            )}
            {imagenQr && pagoQr.resultado === 'PENDIENTE' && <img className="mx-auto my-4 max-h-64 max-w-full" src={imagenQr} alt={esQrSimulado ? 'Código QR simulado' : 'Código QR para pagar'} />}
            <p className="mt-3 font-semibold">Estado: {pagoQr.resultado_display}</p>
            {pagoQr.qr_expira_at && <p className="mt-2 text-sm text-slate-500">Vence: {new Date(pagoQr.qr_expira_at).toLocaleString()}</p>}
            <p className="mt-2 text-sm text-slate-500">{pagoQr.observacion}</p>
            {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
            {pagoQr.resultado === 'PENDIENTE' && <button className="btn-primary mt-5" disabled={enviando} onClick={() => void verificarQr(pagoQr)}>
              {enviando ? 'Procesando…' : esQrSimulado ? 'Simular pago' : 'Comprobar pago'}
            </button>}
          </div>
        </div>
      )}

      {modalPago && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6">
            <button aria-label="Cerrar formulario" className="float-right" onClick={() => setModalPago(false)}><X /></button>
            <h2 className="text-xl font-bold">Registrar pago</h2>
            <p className="mt-2 rounded bg-slate-50 p-3 text-sm text-slate-600">Los planes gratuitos no generan pagos. Una suscripción de 0 BOB ya está activa y no requiere registrar ni validar un pago.</p>
            <div className="mt-5 grid gap-4">
              <Select label="Suscripción" value={formPago.suscripcion} error={errores.suscripcion}
                onChange={(v) => setFormPago({ ...formPago, suscripcion: v })}
                opciones={[['', 'Seleccione'], ...suscripcionesPagables.map((s) => [String(s.id), `${s.colegio_nombre} — ${s.plan_nombre} (${s.estado_display})`])]} />
              <Select label="Método" value={formPago.metodo}
                onChange={(v) => setFormPago({ ...formPago, metodo: v })}
                opciones={metodos.filter((metodo) => metodo.activo && !metodosEnLinea.includes(metodo.codigo)).map((metodo) => [metodo.codigo, metodo.nombre])} />
              <Campo label="Referencia" value={formPago.referencia} error={errores.referencia}
                onChange={(v) => setFormPago({ ...formPago, referencia: v })} />
              <Campo label="Monto (moneda de la suscripción)" type="number" value={formPago.monto} error={errores.monto}
                onChange={(v) => setFormPago({ ...formPago, monto: v })} />
              <Campo label="Observación (opcional)" value={formPago.observacion}
                onChange={(v) => setFormPago({ ...formPago, observacion: v })} />
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button className="btn-secondary" onClick={() => setModalPago(false)}>Cancelar</button>
              <button className="btn-primary" disabled={enviando} onClick={() => void guardarPago()}>
                {enviando ? 'Registrando...' : 'Registrar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {modalMetodo && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6"><button aria-label="Cerrar método" className="float-right" onClick={() => setModalMetodo(false)}><X /></button>
            <h2 className="text-xl font-bold">{editandoMetodo ? 'Editar' : 'Configurar'} método de pago</h2><p className="mt-1 text-sm text-slate-500">Solo los métodos activos estarán disponibles para nuevos registros y pagos.</p>
            <div className="mt-5 grid gap-4"><Select label="Código" value={formMetodo.codigo} onChange={(codigo) => setFormMetodo({ ...formMetodo, codigo })} opciones={editandoMetodo ? [[formMetodo.codigo, formMetodo.codigo]] : [['TRANSFERENCIA', 'Transferencia bancaria'], ['TARJETA', 'Tarjeta'], ['EFECTIVO', 'Efectivo'], ['PASARELA', 'Pasarela de pago']]} />
              <Campo label="Nombre visible" value={formMetodo.nombre} error={errores.nombre_metodo} onChange={(nombre) => setFormMetodo({ ...formMetodo, nombre })}/><Campo label="Descripción" value={formMetodo.descripcion} onChange={(descripcion) => setFormMetodo({ ...formMetodo, descripcion })}/>
              <label className="flex gap-2 text-sm"><input type="checkbox" checked={formMetodo.activo} onChange={(e) => setFormMetodo({ ...formMetodo, activo: e.target.checked })}/> Disponible para nuevos pagos</label>
            </div><div className="mt-6 flex justify-end gap-2"><button className="btn-secondary" onClick={() => setModalMetodo(false)}>Cancelar</button><button className="btn-primary" disabled={enviando} onClick={() => void guardarMetodo()}>{enviando ? 'Guardando...' : 'Guardar'}</button></div>
          </div>
        </div>
      )}

      {modalPlan && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/50 p-4">
          <div className="w-full max-w-2xl rounded-2xl bg-white p-6">
            <button aria-label="Cerrar formulario" className="float-right" onClick={() => setModalPlan(false)}><X /></button>
            <h2 className="text-xl font-bold">{editandoPlan ? 'Editar' : 'Nuevo'} plan</h2>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <Campo label="Nombre" value={formPlan.nombre} error={errores.nombre}
                onChange={(v) => setFormPlan({ ...formPlan, nombre: v })} />
              <Campo label="Precio" type="number" value={formPlan.precio} error={errores.precio}
                onChange={(v) => setFormPlan({ ...formPlan, precio: v })} />
              <Select label="Moneda" value={formPlan.moneda} onChange={(v) => setFormPlan({ ...formPlan, moneda: v })} opciones={[[ 'BOB', 'BOB' ], [ 'USD', 'USD' ]]} />
              <Select label="Periodicidad" value={formPlan.periodicidad}
                onChange={(v) => setFormPlan({ ...formPlan, periodicidad: v })}
                opciones={PERIODICIDADES} />
              <Select label="Estado" value={formPlan.estado}
                onChange={(v) => setFormPlan({ ...formPlan, estado: v })}
                opciones={[['ACTIVO', 'Activo'], ['INACTIVO', 'Inactivo']]} />
              <Campo label="Límite de usuarios (0 = sin límite)" type="number" value={formPlan.limite_usuarios}
                onChange={(v) => setFormPlan({ ...formPlan, limite_usuarios: v })} />
              <Campo label="Límite de unidades (0 = sin límite)" type="number" value={formPlan.limite_unidades}
                onChange={(v) => setFormPlan({ ...formPlan, limite_unidades: v })} />
              <label className="text-sm font-medium sm:col-span-2">Descripción
                <textarea
                  aria-label="Descripción"
                  value={formPlan.descripcion}
                  onChange={(e) => setFormPlan({ ...formPlan, descripcion: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                  rows={2}
                />
              </label>
              <label className="text-sm font-medium sm:col-span-2">Módulos habilitados (separados por coma; vacío = todos)
                <input
                  aria-label="Módulos habilitados"
                  value={formPlan.modulos_habilitados}
                  onChange={(e) => setFormPlan({ ...formPlan, modulos_habilitados: e.target.value })}
                  placeholder="colegio, unidad-educativa, usuario, estudiante"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button className="btn-secondary" onClick={() => setModalPlan(false)}>Cancelar</button>
              <button className="btn-primary" disabled={enviando} onClick={() => void guardarPlan()}>
                {enviando ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {!esPlataforma && estadoColegio === null && !cargando && (
        <p className="flex items-center gap-2 rounded-2xl bg-slate-50 p-4 text-sm text-slate-500">
          <AlertTriangle size={17} />No se pudo determinar el estado de la suscripción del colegio.
        </p>
      )}
    </section>
  )
}

function Campo({ label, value, onChange, type = 'text', error }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; error?: string
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <input
        aria-label={label}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
      />
      {error && <span className="block text-xs text-red-600">{error}</span>}
    </label>
  )
}

function Select({ label, value, onChange, opciones, error }: {
  label: string; value: string; onChange: (v: string) => void; opciones: string[][]; error?: string
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
      >
        {opciones.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
      </select>
      {error && <span className="block text-xs text-red-600">{error}</span>}
    </label>
  )
}

function mensajeDominio(data: unknown) {
  if (!data || typeof data !== 'object') return 'Revise los datos ingresados.'
  return Object.entries(data as Record<string, unknown>)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : String(v)}`)
    .join(' ')
}

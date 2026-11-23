import axios from 'axios'
import { CalendarRange, CheckCircle2, Eye, Pencil, Plus, Power, Users } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import { cargarCatalogoPaginado } from '../../api/catalogosPaginados'
import {
  activarPlan, actualizarPlan, asignarPlan, crearPlan, desactivarPlan, formatoMonto, generarCuotas, listarPlanes,
  type NivelEducativo, type PlanPago, type ResultadoAsignacion,
} from '../../api/finanzas'
import { Paginacion } from '../auditoria/AuditoriaPage'
import { Avisos, Campo, Estado, Modal, Tabla } from './comunes'
import { errorTexto, NIVELES, PAGE_SIZE, type ContextoFinanzas } from './utilidades'

type Dialogo =
  | { tipo: 'formulario'; plan: PlanPago | null }
  | { tipo: 'cuotas' | 'asignar' | 'detalle'; plan: PlanPago }

const FORMULARIO_VACIO = { nombre: '', descripcion: '', nivel: '', monto: '', cuotas: '10' }

export default function PlanesPagoTab({ contexto }: { contexto: ContextoFinanzas }) {
  const { can } = useAuth()
  const { unidadId, calendarioId } = contexto
  const [planes, setPlanes] = useState<PlanPago[]>([])
  const [total, setTotal] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [estado, setEstado] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [dialogo, setDialogo] = useState<Dialogo | null>(null)
  const [formulario, setFormulario] = useState(FORMULARIO_VACIO)
  const [fecha, setFecha] = useState('')
  const [curso, setCurso] = useState('')
  const [cursos, setCursos] = useState<{ id: number; nombre: string }[]>([])
  const [resultado, setResultado] = useState<ResultadoAsignacion | null>(null)
  const [enviando, setEnviando] = useState(false)
  const consulta = useRef<AbortController | null>(null)

  const cargar = useCallback(async () => {
    if (!calendarioId) { setPlanes([]); setTotal(0); return }
    consulta.current?.abort(); const controller = new AbortController(); consulta.current = controller
    setCargando(true); setError('')
    try {
      const { data } = await listarPlanes({ unidad_educativa: unidadId, calendario_academico: calendarioId, estado, page: pagina, page_size: PAGE_SIZE }, controller.signal)
      if (!controller.signal.aborted) { setPlanes(data.results); setTotal(data.count) }
    } catch (e) { if (!controller.signal.aborted && !axios.isCancel(e)) setError(errorTexto(e, 'No fue posible cargar los planes de pago.')) }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }, [unidadId, calendarioId, estado, pagina])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar(); return () => consulta.current?.abort() }, [cargar])

  const abrir = (nuevo: Dialogo) => {
    setError(''); setExito(''); setResultado(null)
    if (nuevo.tipo === 'formulario') {
      const p = nuevo.plan
      setFormulario(p ? { nombre: p.nombre, descripcion: p.descripcion, nivel: p.nivel_educativo ?? '', monto: p.monto_total, cuotas: String(p.numero_cuotas) } : FORMULARIO_VACIO)
    }
    if (nuevo.tipo === 'cuotas') setFecha(nuevo.plan.cuotas[0]?.fecha_vencimiento ?? '')
    if (nuevo.tipo === 'asignar') {
      setCurso('')
      cargarCatalogoPaginado<{ id: number; nombre: string }>('/academico/cursos/', { unidad_educativa: unidadId })
        .then(setCursos).catch(e => setError(errorTexto(e, 'No fue posible cargar los cursos.')))
    }
    setDialogo(nuevo)
  }

  const ejecutar = async (accion: () => Promise<unknown>, mensaje: string, cerrar = true) => {
    if (enviando) return
    setEnviando(true); setError('')
    try { await accion(); if (cerrar) setDialogo(null); setExito(mensaje); await cargar() }
    catch (e) { setError(errorTexto(e, 'No fue posible completar la operación.')) }
    finally { setEnviando(false) }
  }

  const guardar = () => {
    if (dialogo?.tipo !== 'formulario' || !calendarioId) return
    const nombre = formulario.nombre.trim().replace(/\s+/g, ' ')
    if (!nombre || !(Number(formulario.monto) > 0)) { setError('Complete el nombre y un monto total mayor a cero.'); return }
    const datos = {
      unidad_educativa: unidadId, calendario_academico: calendarioId, nombre, descripcion: formulario.descripcion.trim(),
      nivel_educativo: (formulario.nivel || null) as NivelEducativo | null, monto_total: formulario.monto, numero_cuotas: Number(formulario.cuotas),
    }
    const plan = dialogo.plan
    void ejecutar(() => plan ? actualizarPlan(plan.id, plan.estado === 'BORRADOR' ? datos : { nombre, descripcion: datos.descripcion }) : crearPlan(datos), 'Plan de pago guardado.')
  }

  const asignar = (plan: PlanPago) => {
    if (!curso) { setError('Seleccione un curso.'); return }
    void ejecutar(async () => { const { data } = await asignarPlan(plan.id, { curso: Number(curso) }); setResultado(data) }, 'Plan asignado al curso.', false)
  }

  if (!calendarioId) return <p className="rounded-xl bg-amber-50 p-4 text-amber-800">Seleccione una gestión para ver sus planes de pago.</p>
  const puedeCrear = can('plan-pago', 'crear'), puedeEditar = can('plan-pago', 'editar')
  const puedeDesactivar = can('plan-pago', 'desactivar'), puedeAsignar = can('plan-pago', 'asignar')
  const bloqueado = dialogo?.tipo === 'formulario' && dialogo.plan !== null && dialogo.plan.estado !== 'BORRADOR'

  return <div className="space-y-4">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <Campo label="Estado del plan">
        <select aria-label="Estado del plan" value={estado} onChange={e => { setEstado(e.target.value); setPagina(1) }} className="w-48 rounded-lg border p-2">
          <option value="">Todos</option><option value="BORRADOR">Borrador</option><option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option>
        </select>
      </Campo>
      {puedeCrear && <button className="btn-primary" onClick={() => abrir({ tipo: 'formulario', plan: null })}><Plus size={17} />Nuevo plan</button>}
    </div>
    <Avisos error={dialogo ? '' : error} exito={exito} reintentar={() => void cargar()} />
    <Tabla columnas={['Plan', 'Nivel', 'Monto total', 'Cuotas', 'Estudiantes', 'Estado', 'Acciones']} cargando={cargando} vacio={planes.length === 0}>
      {planes.map(plan => <tr key={plan.id} className="border-t">
        <td className="p-4"><p className="font-medium">{plan.nombre}</p>{plan.descripcion && <p className="text-xs text-slate-500">{plan.descripcion}</p>}</td>
        <td className="p-4">{plan.nivel_display ?? 'Todos'}</td>
        <td className="p-4">{formatoMonto(plan.monto_total, plan.moneda)}</td>
        <td className="p-4">{plan.cuotas.length}/{plan.numero_cuotas}</td>
        <td className="p-4">{plan.estudiantes_asignados}</td>
        <td className="p-4"><Estado valor={plan.estado} /></td>
        <td className="p-4"><div className="flex flex-wrap gap-3">
          <button aria-label={`Ver cuotas ${plan.nombre}`} title="Ver cuotas" onClick={() => abrir({ tipo: 'detalle', plan })}><Eye size={18} /></button>
          {puedeEditar && plan.estado !== 'INACTIVO' && <button aria-label={`Editar ${plan.nombre}`} title="Editar" onClick={() => abrir({ tipo: 'formulario', plan })}><Pencil size={18} /></button>}
          {puedeEditar && plan.estado === 'BORRADOR' && <>
            <button aria-label={`Generar cuotas ${plan.nombre}`} title="Generar cuotas" onClick={() => abrir({ tipo: 'cuotas', plan })}><CalendarRange size={18} /></button>
            <button aria-label={`Activar ${plan.nombre}`} title="Activar" className="text-emerald-700" disabled={enviando}
              onClick={() => { if (window.confirm(`¿Activar ${plan.nombre}? Luego no podrá cambiar montos ni cuotas.`)) void ejecutar(() => activarPlan(plan.id), 'Plan activado.') }}><CheckCircle2 size={18} /></button>
          </>}
          {puedeAsignar && plan.estado === 'ACTIVO' && <button aria-label={`Asignar ${plan.nombre}`} title="Asignar a curso" className="text-brand-700" onClick={() => abrir({ tipo: 'asignar', plan })}><Users size={18} /></button>}
          {puedeDesactivar && plan.estado !== 'INACTIVO' && <button aria-label={`Desactivar ${plan.nombre}`} title="Desactivar" className="text-red-600" disabled={enviando}
            onClick={() => { if (window.confirm(`¿Desactivar ${plan.nombre}? Las obligaciones ya generadas se conservan.`)) void ejecutar(() => desactivarPlan(plan.id), 'Plan desactivado.') }}><Power size={18} /></button>}
        </div></td>
      </tr>)}
    </Tabla>
    <Paginacion pagina={pagina} paginas={Math.max(1, Math.ceil(total / PAGE_SIZE))} cambiar={setPagina} />

    {dialogo?.tipo === 'formulario' && <Modal title={dialogo.plan ? 'Editar plan de pago' : 'Nuevo plan de pago'} close={() => setDialogo(null)}>
      <div className="space-y-3">
        {bloqueado && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">El plan ya está activo: solo puede cambiar nombre y descripción.</p>}
        <Campo label="Nombre"><input aria-label="Nombre del plan" value={formulario.nombre} onChange={e => setFormulario({ ...formulario, nombre: e.target.value })} className="w-full rounded-lg border p-2" autoFocus /></Campo>
        <Campo label="Descripción"><textarea aria-label="Descripción del plan" value={formulario.descripcion} onChange={e => setFormulario({ ...formulario, descripcion: e.target.value })} className="w-full rounded-lg border p-2" rows={2} /></Campo>
        <Campo label="Nivel"><select aria-label="Nivel del plan" disabled={bloqueado} value={formulario.nivel} onChange={e => setFormulario({ ...formulario, nivel: e.target.value })} className="w-full rounded-lg border p-2"><option value="">Todos los niveles</option>{NIVELES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></Campo>
        <div className="grid grid-cols-2 gap-3">
          <Campo label="Monto total (Bs)"><input aria-label="Monto total" type="number" min="0.01" step="0.01" disabled={bloqueado} value={formulario.monto} onChange={e => setFormulario({ ...formulario, monto: e.target.value })} className="w-full rounded-lg border p-2" /></Campo>
          <Campo label="Número de cuotas"><select aria-label="Número de cuotas" disabled={bloqueado} value={formulario.cuotas} onChange={e => setFormulario({ ...formulario, cuotas: e.target.value })} className="w-full rounded-lg border p-2">{Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}</select></Campo>
        </div>
        {Number(formulario.monto) > 0 && <p className="text-sm text-slate-500">Cuota aproximada: {formatoMonto(Number(formulario.monto) / Number(formulario.cuotas))}</p>}
      </div>
      <Avisos error={error} exito="" />
      <div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={() => setDialogo(null)}>Cancelar</button><button className="btn-primary" disabled={enviando} onClick={guardar}>{enviando ? 'Guardando...' : 'Guardar'}</button></div>
    </Modal>}

    {dialogo?.tipo === 'cuotas' && <Modal title={`Generar cuotas: ${dialogo.plan.nombre}`} close={() => setDialogo(null)}>
      <p className="mb-3 text-sm text-slate-600">Se crearán {dialogo.plan.numero_cuotas} cuotas mensuales de {formatoMonto(Number(dialogo.plan.monto_total) / dialogo.plan.numero_cuotas)} aprox. Si ya existían, se reemplazan.</p>
      <Campo label="Primer vencimiento"><input aria-label="Primer vencimiento" type="date" value={fecha} onChange={e => setFecha(e.target.value)} className="w-full rounded-lg border p-2" /></Campo>
      <Avisos error={error} exito="" />
      <div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={() => setDialogo(null)}>Cancelar</button>
        <button className="btn-primary" disabled={enviando || !fecha} onClick={() => void ejecutar(() => generarCuotas(dialogo.plan.id, fecha), 'Cuotas generadas.')}>{enviando ? 'Generando...' : 'Generar cuotas'}</button></div>
    </Modal>}

    {dialogo?.tipo === 'asignar' && <Modal title={`Asignar: ${dialogo.plan.nombre}`} close={() => setDialogo(null)}>
      <p className="mb-3 text-sm text-slate-600">Se generan las cuotas para cada estudiante activo del curso, aplicando su beca vigente. Volver a asignar no duplica cuotas.</p>
      <Campo label="Curso"><select aria-label="Curso a asignar" value={curso} onChange={e => setCurso(e.target.value)} className="w-full rounded-lg border p-2"><option value="">Seleccione un curso</option>{cursos.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></Campo>
      {resultado && <div role="status" className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
        <p>{resultado.estudiantes} estudiante(s): {resultado.obligaciones_creadas} cuota(s) nuevas, {resultado.obligaciones_existentes} ya existían.</p>
        {resultado.rechazados.length > 0 && <p className="mt-1 text-amber-800">{resultado.rechazados.length} estudiante(s) omitidos (otro nivel o inactivos).</p>}
      </div>}
      <Avisos error={error} exito="" />
      <div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={() => setDialogo(null)}>Cerrar</button>
        <button className="btn-primary" disabled={enviando || !curso} onClick={() => asignar(dialogo.plan)}>{enviando ? 'Asignando...' : 'Asignar plan'}</button></div>
    </Modal>}

    {dialogo?.tipo === 'detalle' && <Modal title={`Cuotas: ${dialogo.plan.nombre}`} close={() => setDialogo(null)} ancho="max-w-lg">
      {dialogo.plan.cuotas.length === 0 ? <p className="text-sm text-slate-600">El plan aún no tiene cuotas generadas.</p>
        : <table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-2">Concepto</th><th className="py-2">Vence</th><th className="py-2 text-right">Monto</th></tr></thead>
          <tbody>{dialogo.plan.cuotas.map(c => <tr key={c.id} className="border-b"><td className="py-2">{c.concepto}</td><td className="py-2">{c.fecha_vencimiento}</td><td className="py-2 text-right">{formatoMonto(c.monto)}</td></tr>)}</tbody></table>}
    </Modal>}
  </div>
}

import axios from 'axios'
import { Award, Pencil, Plus, Power, UserMinus } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import {
  actualizarBeca, cambiarEstadoBeca, crearBeca, formatoMonto, listarAsignacionesBeca, listarBecas,
  otorgarBeca, revocarBeca, type AsignacionBeca, type Beca, type EstudianteElegible, type TipoDescuento,
} from '../../api/finanzas'
import { Paginacion } from '../auditoria/AuditoriaPage'
import { Avisos, BuscadorEstudiante, Campo, Estado, Modal, Tabla } from './comunes'
import { errorTexto, PAGE_SIZE, type ContextoFinanzas } from './utilidades'

const FORMULARIO_VACIO = { nombre: '', descripcion: '', tipo: 'PORCENTAJE' as TipoDescuento, valor: '' }
const descuentoTexto = (tipo: TipoDescuento, valor: string) => tipo === 'PORCENTAJE' ? `${Number(valor)}%` : `${formatoMonto(valor)} por cuota`

export default function BecasTab({ contexto }: { contexto: ContextoFinanzas }) {
  const { can } = useAuth()
  const { unidadId, calendarioId } = contexto
  const [becas, setBecas] = useState<Beca[]>([])
  const [asignaciones, setAsignaciones] = useState<AsignacionBeca[]>([])
  const [totalAsignaciones, setTotalAsignaciones] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [modalBeca, setModalBeca] = useState<Beca | 'nueva' | null>(null)
  const [modalOtorgar, setModalOtorgar] = useState(false)
  const [formulario, setFormulario] = useState(FORMULARIO_VACIO)
  const [becaElegida, setBecaElegida] = useState('')
  const [estudiante, setEstudiante] = useState<EstudianteElegible | null>(null)
  const [motivo, setMotivo] = useState('')
  const [enviando, setEnviando] = useState(false)
  const consulta = useRef<AbortController | null>(null)

  const cargar = useCallback(async () => {
    consulta.current?.abort(); const controller = new AbortController(); consulta.current = controller
    setCargando(true); setError('')
    try {
      const [respuestaBecas, respuestaAsignaciones] = await Promise.all([
        listarBecas({ unidad_educativa: unidadId, page_size: 100 }, controller.signal),
        calendarioId
          ? listarAsignacionesBeca({ unidad_educativa: unidadId, calendario_academico: calendarioId, page: pagina, page_size: PAGE_SIZE }, controller.signal)
          : Promise.resolve(null),
      ])
      if (controller.signal.aborted) return
      setBecas(respuestaBecas.data.results)
      setAsignaciones(respuestaAsignaciones?.data.results ?? []); setTotalAsignaciones(respuestaAsignaciones?.data.count ?? 0)
    } catch (e) { if (!controller.signal.aborted && !axios.isCancel(e)) setError(errorTexto(e, 'No fue posible cargar las becas.')) }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }, [unidadId, calendarioId, pagina])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar(); return () => consulta.current?.abort() }, [cargar])

  const ejecutar = async (accion: () => Promise<unknown>, mensaje: string, cerrar: () => void = () => undefined) => {
    if (enviando) return
    setEnviando(true); setError('')
    try { await accion(); cerrar(); setExito(mensaje); await cargar() }
    catch (e) { setError(errorTexto(e, 'No fue posible completar la operación.')) }
    finally { setEnviando(false) }
  }

  const abrirBeca = (beca: Beca | 'nueva') => {
    setError(''); setExito('')
    setFormulario(beca === 'nueva' ? FORMULARIO_VACIO : { nombre: beca.nombre, descripcion: beca.descripcion, tipo: beca.tipo_descuento, valor: beca.valor })
    setModalBeca(beca)
  }
  const guardarBeca = () => {
    const nombre = formulario.nombre.trim().replace(/\s+/g, ' ')
    if (!nombre || !(Number(formulario.valor) > 0)) { setError('Complete el nombre y un valor mayor a cero.'); return }
    if (formulario.tipo === 'PORCENTAJE' && Number(formulario.valor) > 100) { setError('El porcentaje no puede superar 100.'); return }
    const datos = { unidad_educativa: unidadId, nombre, descripcion: formulario.descripcion.trim(), tipo_descuento: formulario.tipo, valor: formulario.valor }
    void ejecutar(() => modalBeca === 'nueva' || !modalBeca ? crearBeca(datos) : actualizarBeca(modalBeca.id, datos), 'Beca guardada.', () => setModalBeca(null))
  }

  const abrirOtorgar = () => {
    setError(''); setExito(''); setBecaElegida(''); setEstudiante(null); setMotivo('')
    setModalOtorgar(true)
  }
  const otorgar = () => {
    if (!calendarioId || !becaElegida || !estudiante || !motivo.trim()) { setError('Seleccione beca, estudiante y escriba el motivo.'); return }
    void ejecutar(() => otorgarBeca({ beca: Number(becaElegida), estudiante: estudiante.id, calendario_academico: calendarioId, motivo: motivo.trim() }),
      `Beca otorgada a ${estudiante.nombre}. Sus cuotas pendientes se recalcularon.`, () => setModalOtorgar(false))
  }
  const revocar = (asignacion: AsignacionBeca) => {
    const razon = window.prompt(`Motivo para revocar la beca de ${asignacion.estudiante_nombre}:`)
    if (razon?.trim()) void ejecutar(() => revocarBeca(asignacion.id, razon.trim()), 'Beca revocada. Las cuotas pendientes vuelven a su monto original.')
  }

  const puedeCrear = can('beca', 'crear'), puedeEditar = can('beca', 'editar')
  const puedeDesactivar = can('beca', 'desactivar'), puedeAsignar = can('beca', 'asignar')
  const activas = becas.filter(b => b.estado === 'ACTIVO')

  return <div className="space-y-6">
    <Avisos error={modalBeca || modalOtorgar ? '' : error} exito={exito} reintentar={() => void cargar()} />
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Catálogo de becas y descuentos</h2>
        {puedeCrear && <button className="btn-primary" onClick={() => abrirBeca('nueva')}><Plus size={17} />Nueva beca</button>}
      </div>
      <Tabla columnas={['Beca', 'Descuento', 'Estudiantes con beca', 'Estado', 'Acciones']} cargando={cargando} vacio={becas.length === 0}>
        {becas.map(beca => <tr key={beca.id} className="border-t">
          <td className="p-4"><p className="font-medium">{beca.nombre}</p>{beca.descripcion && <p className="text-xs text-slate-500">{beca.descripcion}</p>}</td>
          <td className="p-4">{descuentoTexto(beca.tipo_descuento, beca.valor)}</td>
          <td className="p-4">{beca.asignaciones_vigentes}</td>
          <td className="p-4"><Estado valor={beca.estado} /></td>
          <td className="p-4"><div className="flex gap-3">
            {puedeEditar && <button aria-label={`Editar beca ${beca.nombre}`} title="Editar" onClick={() => abrirBeca(beca)}><Pencil size={18} /></button>}
            {puedeDesactivar && <button aria-label={`${beca.estado === 'ACTIVO' ? 'Desactivar' : 'Activar'} beca ${beca.nombre}`} title={beca.estado === 'ACTIVO' ? 'Desactivar' : 'Activar'}
              className={beca.estado === 'ACTIVO' ? 'text-red-600' : 'text-emerald-700'} disabled={enviando}
              onClick={() => void ejecutar(() => cambiarEstadoBeca(beca.id, beca.estado !== 'ACTIVO'), beca.estado === 'ACTIVO' ? 'Beca desactivada.' : 'Beca activada.')}><Power size={18} /></button>}
          </div></td>
        </tr>)}
      </Tabla>
    </section>

    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Becas otorgadas en la gestión</h2>
        {puedeAsignar && <button className="btn-primary" disabled={!calendarioId || activas.length === 0} onClick={abrirOtorgar}><Award size={17} />Otorgar beca</button>}
      </div>
      {!calendarioId ? <p className="rounded-xl bg-amber-50 p-4 text-amber-800">Seleccione una gestión para ver las becas otorgadas.</p> : <>
        <Tabla columnas={['Estudiante', 'Curso', 'Beca', 'Motivo', 'Otorgada por', 'Estado', 'Acciones']} cargando={cargando} vacio={asignaciones.length === 0}>
          {asignaciones.map(a => <tr key={a.id} className="border-t">
            <td className="p-4 font-medium">{a.estudiante_nombre}</td>
            <td className="p-4">{a.curso_nombre ?? '—'}</td>
            <td className="p-4">{a.beca_nombre}<p className="text-xs text-slate-500">{descuentoTexto(a.tipo_descuento, a.valor)}</p></td>
            <td className="p-4">{a.motivo}{a.motivo_revocacion && <p className="text-xs text-red-600">Revocada: {a.motivo_revocacion}</p>}</td>
            <td className="p-4">{a.asignado_por_nombre || '—'}</td>
            <td className="p-4"><Estado valor={a.estado} /></td>
            <td className="p-4">{puedeAsignar && a.estado === 'VIGENTE' && <button aria-label={`Revocar beca de ${a.estudiante_nombre}`} title="Revocar" className="text-red-600" disabled={enviando} onClick={() => revocar(a)}><UserMinus size={18} /></button>}</td>
          </tr>)}
        </Tabla>
        <Paginacion pagina={pagina} paginas={Math.max(1, Math.ceil(totalAsignaciones / PAGE_SIZE))} cambiar={setPagina} />
      </>}
    </section>

    {modalBeca && <Modal title={modalBeca === 'nueva' ? 'Nueva beca' : 'Editar beca'} close={() => setModalBeca(null)}>
      <div className="space-y-3">
        {modalBeca !== 'nueva' && modalBeca.asignaciones_vigentes > 0 && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Tiene estudiantes con esta beca vigente: no se puede cambiar el descuento.</p>}
        <Campo label="Nombre"><input aria-label="Nombre de beca" value={formulario.nombre} onChange={e => setFormulario({ ...formulario, nombre: e.target.value })} className="w-full rounded-lg border p-2" autoFocus /></Campo>
        <Campo label="Descripción / requisitos"><textarea aria-label="Descripción de beca" value={formulario.descripcion} onChange={e => setFormulario({ ...formulario, descripcion: e.target.value })} className="w-full rounded-lg border p-2" rows={2} /></Campo>
        <div className="grid grid-cols-2 gap-3">
          <Campo label="Tipo de descuento"><select aria-label="Tipo de descuento" value={formulario.tipo} onChange={e => setFormulario({ ...formulario, tipo: e.target.value as TipoDescuento })} className="w-full rounded-lg border p-2"><option value="PORCENTAJE">Porcentaje</option><option value="MONTO_FIJO">Monto fijo por cuota</option></select></Campo>
          <Campo label={formulario.tipo === 'PORCENTAJE' ? 'Porcentaje (%)' : 'Monto (Bs)'}><input aria-label="Valor del descuento" type="number" min="0.01" step="0.01" value={formulario.valor} onChange={e => setFormulario({ ...formulario, valor: e.target.value })} className="w-full rounded-lg border p-2" /></Campo>
        </div>
      </div>
      <Avisos error={error} exito="" />
      <div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={() => setModalBeca(null)}>Cancelar</button><button className="btn-primary" disabled={enviando} onClick={guardarBeca}>{enviando ? 'Guardando...' : 'Guardar'}</button></div>
    </Modal>}

    {modalOtorgar && <Modal title="Otorgar beca" close={() => setModalOtorgar(false)} ancho="max-w-lg">
      <div className="space-y-3">
        <Campo label="Beca"><select aria-label="Beca a otorgar" value={becaElegida} onChange={e => setBecaElegida(e.target.value)} className="w-full rounded-lg border p-2"><option value="">Seleccione una beca</option>{activas.map(b => <option key={b.id} value={b.id}>{b.nombre} ({descuentoTexto(b.tipo_descuento, b.valor)})</option>)}</select></Campo>
        <div className="text-sm font-medium">Estudiante<div className="mt-1"><BuscadorEstudiante unidadId={unidadId} seleccionado={estudiante} onSeleccionar={setEstudiante} /></div></div>
        <Campo label="Motivo"><textarea aria-label="Motivo de la beca" value={motivo} onChange={e => setMotivo(e.target.value)} className="w-full rounded-lg border p-2" rows={2} /></Campo>
        <p className="text-xs text-slate-500">Las cuotas pendientes del estudiante en esta gestión se recalculan con el descuento; las ya pagadas no cambian.</p>
      </div>
      <Avisos error={error} exito="" />
      <div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={() => setModalOtorgar(false)}>Cancelar</button><button className="btn-primary" disabled={enviando || !estudiante || !becaElegida} onClick={otorgar}>{enviando ? 'Guardando...' : 'Otorgar'}</button></div>
    </Modal>}
  </div>
}

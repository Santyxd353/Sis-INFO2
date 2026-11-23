import { useEffect, useState } from 'react'
import { listarUnidadesCatalogo } from '../../../api/catalogosInstitucionales'
import { listarCalendarios, listarCursos } from '../../../api/asignacionesDocentes'
import { cargarCatalogoPaginado } from '../../../api/catalogosPaginados'
import type { FiltroReporteOperativo } from '../../../api/reportes'
import { useAuth } from '../../../app/contexts/AuthContext'

type Opcion = { id: number; nombre: string }

// La conversión se comparte con ambos constructores de reportes.
// eslint-disable-next-line react-refresh/only-export-components
export function convertirValor(filtro: FiltroReporteOperativo, operador: string, valor: string): string | number | boolean | Array<string | number | boolean> {
  const convertir = (texto: string): string | number | boolean => {
    const v = texto.trim()
    if (!v) throw new Error('Complete el valor del filtro.')
    if (filtro.tipo === 'booleano') {
      if (v !== 'true' && v !== 'false') throw new Error('Seleccione Sí o No.')
      return v === 'true'
    }
    if (filtro.tipo === 'entero' || filtro.tipo === 'decimal') {
      const numero = Number(v)
      if (!Number.isFinite(numero) || (filtro.tipo === 'entero' && (!Number.isSafeInteger(numero) || numero < 0))) throw new Error('Ingrese un número válido.')
      return numero
    }
    if (filtro.tipo === 'fecha' && !/^\d{4}-\d{2}-\d{2}$/.test(v)) throw new Error('Ingrese una fecha válida.')
    return v
  }
  if (operador === 'in') {
    const valores = valor.split(',').map((v) => v.trim()).filter(Boolean)
    if (!valores.length) throw new Error('Seleccione al menos un valor.')
    return valores.map(convertir)
  }
  return convertir(valor)
}

export default function FilterValueInput({ filtro, operador, valor, onChange, error }: { filtro?: FiltroReporteOperativo; operador: string; valor: string; onChange: (valor: string) => void; error?: string }) {
  const { user } = useAuth()
  const [unidades, setUnidades] = useState<Opcion[]>([])
  const [opciones, setOpciones] = useState<Opcion[]>([])
  const [unidad, setUnidad] = useState('')
  const [gestiones, setGestiones] = useState<Opcion[]>([])
  const [gestion, setGestion] = useState('')
  const [errorCatalogo, setErrorCatalogo] = useState('')
  const control = filtro?.control ?? filtro?.tipo
  useEffect(() => {
    if (!['unidad', 'curso', 'periodo', 'materia'].includes(control ?? '')) return
    const controlador = new AbortController()
    listarUnidadesCatalogo(user?.alcance?.colegio_id ?? undefined, controlador.signal).then((items) => {
      if (controlador.signal.aborted) return
      const permitidas = user?.alcance?.tipo === 'UNIDAD' ? items.filter((item) => item.id === user.alcance?.unidad_id) : items
      setUnidades(permitidas)
      if (permitidas.length === 1) setUnidad(String(permitidas[0].id))
    }).catch(() => { if (!controlador.signal.aborted) setErrorCatalogo('No fue posible cargar las unidades autorizadas.') })
    return () => controlador.abort()
  }, [control, user?.alcance?.colegio_id, user?.alcance?.tipo, user?.alcance?.unidad_id])
  useEffect(() => {
    if (!unidad || !['curso', 'periodo', 'materia'].includes(control ?? '')) return
    const controlador = new AbortController()
    const id = Number(unidad)
    if (control === 'periodo') {
      listarCalendarios(id, controlador.signal).then((items) => { if (!controlador.signal.aborted) setGestiones(items.map((item) => ({ id: item.id, nombre: String(item.año) }))) }).catch(() => { if (!controlador.signal.aborted) setErrorCatalogo('No fue posible cargar las gestiones académicas.') })
      return () => controlador.abort()
    }
    const cargar = control === 'curso' ? listarCursos(id, controlador.signal)
      : cargarCatalogoPaginado<Opcion>('/academico/materias/', { unidad_educativa: id }, controlador.signal)
    cargar.then((items) => { if (!controlador.signal.aborted) setOpciones(items) }).catch(() => { if (!controlador.signal.aborted) setErrorCatalogo('No fue posible cargar el catálogo.') })
    return () => controlador.abort()
  }, [control, unidad])
  useEffect(() => {
    if (control !== 'periodo' || !gestion || !unidad) return
    const controlador = new AbortController()
    cargarCatalogoPaginado<Opcion>('/calendario/periodos/', { calendario: Number(gestion) }, controlador.signal).then((items) => { if (!controlador.signal.aborted) setOpciones(items) }).catch(() => { if (!controlador.signal.aborted) setErrorCatalogo('No fue posible cargar los períodos.') })
    return () => controlador.abort()
  }, [control, gestion, unidad])
  const catalogo = control === 'unidad' ? unidades : opciones
  const esCatalogo = ['unidad', 'curso', 'periodo', 'materia'].includes(control ?? '')
  return <div>
    {esCatalogo && control !== 'unidad' && <label className="block text-sm">Unidad educativa<select aria-label="Unidad educativa para filtro" className="mt-1 w-full rounded border p-2" value={unidad} disabled={user?.alcance?.tipo === 'UNIDAD'} onChange={(e) => { setUnidad(e.target.value); setGestion(''); setOpciones([]); setGestiones([]); onChange('') }}><option value="">Seleccione</option>{unidades.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></label>}
    {control === 'periodo' && <label className="block text-sm">Gestión académica<select aria-label="Gestión académica para filtro" className="mt-1 w-full rounded border p-2" value={gestion} disabled={!unidad} onChange={(e) => { setGestion(e.target.value); setOpciones([]); onChange('') }}><option value="">Seleccione</option>{gestiones.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></label>}
    {esCatalogo ? <select aria-label="Valor" className="mt-1 w-full rounded border p-2" disabled={!filtro || (control !== 'unidad' && !unidad) || (control === 'periodo' && !gestion)} multiple={operador === 'in'} value={operador === 'in' ? valor.split(',').filter(Boolean) : valor} onChange={(e) => onChange(operador === 'in' ? Array.from(e.target.selectedOptions, (o) => o.value).join(',') : e.target.value)}>{operador !== 'in' && <option value="">Seleccione</option>}{catalogo.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select>
      : control === 'booleano' || control === 'enumeracion' ? <select aria-label="Valor" className="mt-1 w-full rounded border p-2" disabled={!filtro} multiple={operador === 'in'} value={operador === 'in' ? valor.split(',').filter(Boolean) : valor} onChange={(e) => onChange(operador === 'in' ? Array.from(e.target.selectedOptions, (o) => o.value).join(',') : e.target.value)}>{operador !== 'in' && <option value="">Seleccione</option>}{(control === 'booleano' ? [{ valor: 'true', etiqueta: 'Sí' }, { valor: 'false', etiqueta: 'No' }] : filtro?.opciones ?? []).map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)}</select>
        : <input aria-label="Valor" className="mt-1 w-full rounded border p-2" disabled={!filtro} type={operador === 'in' ? 'text' : control === 'entero' || control === 'decimal' ? 'number' : control === 'fecha' ? 'date' : 'text'} step={control === 'entero' ? '1' : control === 'decimal' ? 'any' : undefined} value={valor} onChange={(e) => onChange(e.target.value)} />}
    {(error || errorCatalogo) && <p role="alert" className="mt-1 text-sm text-red-700">{error || errorCatalogo}</p>}
  </div>
}

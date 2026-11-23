import axios from 'axios'
import { Download, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import FilterValueInput, { convertirValor } from './components/FilterValueInput'
import { normalizarErrores } from './components/erroresReportes'
import { actualizarDefinicionQbe, archivarDefinicionQbe, guardarNombreQbe, previsualizarQbeLibre, catalogoQbe, crearDefinicionQbe, definicionesQbe, exportarQbe, previsualizarQbe, type DefinicionReporteOperativo, type FuenteQbe, type VistaPreviaReporte } from '../../api/reportes'

type Condicion = { id: string; campo: string; operador: string; valor: string; grupo?: string }
type Grupo = { id: string; logica: 'AND' | 'OR' }
const etiquetasOperador: Record<string, string> = { eq: 'Igual', ne: 'Diferente', contains: 'Contiene', startswith: 'Comienza con', endswith: 'Termina con', in: 'En', isnull: 'Es nulo', notnull: 'No es nulo', gt: 'Mayor que', gte: 'Mayor o igual', lt: 'Menor que', lte: 'Menor o igual', before: 'Antes de', after: 'Después de', between: 'Entre', date_gte: 'Desde', date_lte: 'Hasta' }

export default function QbePanel({ onExportado }: { onExportado?: () => void } = {}) {
  const [fuentes, setFuentes] = useState<FuenteQbe[]>([]); const [codigo, setCodigo] = useState('')
  const [columnas, setColumnas] = useState<string[]>([]); const [condiciones, setCondiciones] = useState<Condicion[]>([])
  const [orden, setOrden] = useState<Array<{ campo: string; direccion: 'asc' | 'desc' }>>([]); const [mensaje, setMensaje] = useState('')
  const [definiciones, setDefiniciones] = useState<DefinicionReporteOperativo[]>([])
  const [paginaDefiniciones, setPaginaDefiniciones] = useState(1)
  const [hayMasDefiniciones, setHayMasDefiniciones] = useState(false)
  const [seleccion, setSeleccion] = useState('')
  const [nombre, setNombre] = useState('')
  const [logica, setLogica] = useState<'AND' | 'OR'>('AND')
  const [grupoPrincipalId, setGrupoPrincipalId] = useState<string>(() => crypto.randomUUID())
  const [grupos, setGrupos] = useState<Grupo[]>([])
  const [limite, setLimite] = useState(100)
  const [vista, setVista] = useState<VistaPreviaReporte | null>(null)
  const [erroresCondicion, setErroresCondicion] = useState<Record<string, Partial<Record<'campo' | 'operador' | 'valor', string>>>>({})
  const [errorColumnas, setErrorColumnas] = useState('')
  const [erroresGrupo, setErroresGrupo] = useState<Record<string, string>>({})
  const [erroresCampo, setErroresCampo] = useState<Record<string, string>>({})
  const peticion = useRef<AbortController | null>(null)
  const version = useRef(0)
  useEffect(() => () => { version.current++; peticion.current?.abort() }, [])
  const limpiarError = (id: string, campo: 'campo' | 'operador' | 'valor') => setErroresCondicion((actual) => ({ ...actual, [id]: { ...actual[id], [campo]: undefined } }))
  const fuente = useMemo(() => fuentes.find((item) => item.codigo === codigo), [fuentes, codigo])
  useEffect(() => { Promise.all([catalogoQbe(), definicionesQbe()]).then(([catalogo, guardadas]) => { setFuentes(catalogo.data.results); setDefiniciones(guardadas.data.results); setHayMasDefiniciones(Boolean(guardadas.data.next)); const primera = catalogo.data.results[0]; setCodigo(primera?.codigo ?? ''); setColumnas(primera?.predeterminadas ?? primera?.columnas.slice(0, 3).map((c) => c.campo) ?? []) }).catch((e) => setMensaje(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para este reporte.' : 'No fue posible cargar el catálogo QBE.')) }, [])
  const paginaDefinicionesIr = async (pagina: number) => {
    try { const { data } = await definicionesQbe(pagina); setDefiniciones(data.results); setHayMasDefiniciones(Boolean(data.next)); setPaginaDefiniciones(pagina); setSeleccion('') }
    catch { setMensaje('No fue posible cargar las definiciones.') }
  }
  const cambiarFuente = (nuevo: string) => { version.current++; peticion.current?.abort(); const item = fuentes.find((f) => f.codigo === nuevo); setCodigo(nuevo); setColumnas(item?.predeterminadas ?? item?.columnas.slice(0, 3).map((c) => c.campo) ?? []); setCondiciones([]); setGrupos([]); setSeleccion(''); setOrden([]); setVista(null); setMensaje(''); setErroresCondicion({}); setErrorColumnas(''); setErroresGrupo({}); setErroresCampo({}) }
  const especificacion = () => {
    if (condiciones.some((condicion) => !['isnull', 'notnull'].includes(condicion.operador) && !condicion.valor.trim())) {
      throw new Error('Complete el valor de cada condición o quite las condiciones vacías.')
    }
    const convertir = (condicion: Condicion) => {
      const filtro = fuente?.filtros.find((f) => f.campo === condicion.campo)
      if (!filtro) throw new Error('Seleccione un campo válido.')
      return { id: condicion.id, campo: condicion.campo, operador: condicion.operador, valor: ['isnull', 'notnull'].includes(condicion.operador) ? null : convertirValor(filtro, condicion.operador === 'between' ? 'in' : condicion.operador, condicion.valor) }
    }
    return {
      columnas,
      condiciones: {
        id: grupoPrincipalId, logica,
        condiciones: [...condiciones.filter((c) => !c.grupo).map(convertir), ...grupos.map((grupo) => ({ ...grupo, condiciones: condiciones.filter((c) => c.grupo === grupo.id).map(convertir) }))],
      },
      orden, limite,
    }
  }
  const crear = async () => {
    const vigente = version.current
    const spec = especificacion()
    const existente = definiciones.find((item) => seleccion ? String(item.id) === seleccion : item.codigo_fuente === codigo && item.nombre === `QBE ${fuente?.etiqueta ?? ''}`)
    if (existente) return actualizarDefinicionQbe(existente.id, spec)
    const respuesta = await crearDefinicionQbe({ nombre: `QBE ${fuente?.etiqueta ?? ''}`, codigo_fuente: codigo, especificacion: spec })
    if (vigente === version.current) { setDefiniciones((items) => [...items, respuesta.data]); setSeleccion(String(respuesta.data.id)) }
    return respuesta
  }
  const cargarDefinicion = (id: string) => {
    version.current++; peticion.current?.abort()
    setSeleccion(id)
    const definicion = definiciones.find((item) => String(item.id) === id)
    if (!definicion) return
    setCodigo(definicion.codigo_fuente); setNombre(definicion.nombre)
    const spec = definicion.especificacion as unknown as { columnas: string[]; orden: typeof orden; limite?: number; condiciones: { id?: string; logica?: 'AND' | 'OR'; condiciones?: Array<{ id?: string; campo?: string; operador?: string; valor?: unknown; logica?: 'AND' | 'OR'; condiciones?: Array<{ id?: string; campo: string; operador: string; valor: unknown }> }>; campo?: string; operador?: string; valor?: unknown } }
    const disponible = fuentes.find((item) => item.codigo === definicion.codigo_fuente)
    if (!disponible || spec.columnas.some((campo) => !disponible.columnas.some((columna) => columna.campo === campo))) { setVista(null); setMensaje('La definición guardada utiliza columnas que ya no están disponibles para su perfil.'); setColumnas([]); return }
    setColumnas(spec.columnas); setOrden(spec.orden); setLimite(spec.limite ?? 100); setLogica(spec.condiciones.logica ?? 'AND'); setGrupoPrincipalId(spec.condiciones.id ?? crypto.randomUUID())
    const filas: Condicion[] = []; const nuevos: Grupo[] = []
    const agregar = (c: { id?: string; campo?: string; operador?: string; valor?: unknown }, grupo?: string) => filas.push({ id: c.id ?? crypto.randomUUID(), campo: c.campo ?? '', operador: c.operador ?? 'eq', valor: Array.isArray(c.valor) ? c.valor.join(', ') : String(c.valor ?? ''), grupo })
    if (spec.condiciones.campo) agregar(spec.condiciones)
    for (const hijo of spec.condiciones.condiciones ?? []) {
      if (hijo.campo) agregar(hijo)
      else { const grupo = { id: hijo.id ?? crypto.randomUUID(), logica: hijo.logica ?? 'AND' }; nuevos.push(grupo); for (const c of hijo.condiciones ?? []) agregar(c, grupo.id) }
    }
    setGrupos(nuevos); setCondiciones(filas); setVista(null)
  }
  const guardarDefinicion = async () => {
    try {
      if (!nombre.trim()) { setErroresCampo((actual) => ({ ...actual, nombre: 'El nombre de la definición es obligatorio.' })); return }
      const spec = especificacion()
      const respuesta = seleccion ? await guardarNombreQbe(Number(seleccion), nombre, spec) : await crearDefinicionQbe({ nombre, codigo_fuente: codigo, especificacion: spec })
      setDefiniciones((items) => [...items.filter((item) => item.id !== respuesta.data.id), respuesta.data]); setSeleccion(String(respuesta.data.id)); setMensaje('Definición guardada.')
    } catch (error) { mostrarError(error, 'No fue posible guardar la definición.') }
  }
  const archivarDefinicion = async () => {
    try { await archivarDefinicionQbe(Number(seleccion)); setDefiniciones((items) => items.filter((item) => String(item.id) !== seleccion)); setSeleccion(''); setMensaje('Definición archivada.') }
    catch { setMensaje('No fue posible archivar la definición.') }
  }
  const mostrarError = (error: unknown, alternativo: string) => {
      const ids = condiciones.map((condicion) => condicion.id)
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 403) { setMensaje('No tiene permiso para este reporte.'); return }
        const errores = normalizarErrores(error.response?.data)
        for (const item of errores) {
          const indice = item.ruta.find((parte) => typeof parte === 'number')
          const id = item.ruta.find((parte) => typeof parte === 'string' && ids.includes(parte))
          const campo = item.ruta.find((parte) => parte === 'campo' || parte === 'operador' || parte === 'valor')
          const idCondicion = typeof id === 'string' ? id : typeof indice === 'number' ? ids[indice] : undefined
          if (idCondicion) {
            const clave = campo === 'campo' || campo === 'operador' || campo === 'valor' ? campo : 'valor'
            setErroresCondicion((actual) => ({ ...actual, [idCondicion]: { ...actual[idCondicion], [clave]: item.mensaje } }))
          } else if (item.ruta.some((p) => typeof p === 'string' && grupos.some((g) => g.id === p))) {
            const grupo = item.ruta.find((p) => typeof p === 'string' && grupos.some((g) => g.id === p)) as string
            setErroresGrupo((actual) => ({ ...actual, [grupo]: item.mensaje }))
          } else if (item.ruta.includes('columnas')) setErrorColumnas(item.mensaje)
          else if (item.ruta.includes('nombre') || item.ruta.includes('orden') || item.ruta.includes('limite')) setErroresCampo((actual) => ({ ...actual, [String(item.ruta.find((p) => p === 'nombre' || p === 'orden' || p === 'limite'))]: item.mensaje }))
          else setMensaje(item.mensaje)
        }
        if (!errores.length) setMensaje(alternativo)
      } else setMensaje(error instanceof Error ? error.message : alternativo)
  }
  const ejecutar = async (formato?: 'CSV' | 'PDF') => {
    const vigente = version.current
    setErroresCondicion({}); setErroresGrupo({}); setErroresCampo({}); setErrorColumnas(''); setMensaje('')
    try {
      const { data } = await crear()
      if (vigente !== version.current) return
      if (formato) {
        const archivo = await exportarQbe(data.id, formato)
        const url = URL.createObjectURL(archivo.data as Blob)
        const enlace = document.createElement('a')
        enlace.href = url
        enlace.download = `qbe.${formato.toLowerCase()}`
        enlace.click()
        URL.revokeObjectURL(url)
        onExportado?.()
      } else {
        peticion.current?.abort(); peticion.current = new AbortController()
        const vista = await previsualizarQbe(data.id, peticion.current.signal)
        if (vigente !== version.current) return
        setVista(vista.data)
        setMensaje(`${vista.data.cantidad} fila(s) en la vista previa.`)
      }
    } catch (error) {
      if (vigente === version.current && !axios.isCancel(error)) mostrarError(error, 'No fue posible ejecutar la consulta QBE.')
    }
  }
  const previsualizarLibre = async () => {
    const vigente = version.current; peticion.current?.abort(); peticion.current = new AbortController()
    try { const respuesta = await previsualizarQbeLibre(codigo, especificacion(), peticion.current.signal); if (vigente === version.current) setVista(respuesta.data) }
    catch (error) { if (vigente === version.current && !axios.isCancel(error)) mostrarError(error, 'No fue posible generar la vista previa.') }
  }
  return <section className="mb-8 space-y-4 rounded-2xl bg-white p-4 shadow-sm" aria-labelledby="qbe-titulo"><h2 id="qbe-titulo" className="text-lg font-semibold">Consulta personalizada (QBE)</h2><p className="text-sm text-slate-500">Construya un reporte seleccionando datos, filtros y ordenamiento sin escribir SQL.</p><p className="text-sm text-slate-600">QBE significa Consulta por Ejemplo. Seleccione qué información desea ver y establezca condiciones; el sistema construirá la consulta de forma segura.</p>{mensaje && <p role="status" className="mb-2 text-sm">{mensaje}</p>}
    <section className="space-y-3 rounded-xl border border-slate-200 p-4 [&_button]:mr-2 [&_button]:rounded-lg [&_button]:border [&_button]:px-3 [&_button]:py-2 [&_button]:text-sm [&_button:disabled]:opacity-50 [&_label]:block [&_select]:mt-1 [&_select]:block [&_select]:w-full [&_select]:rounded [&_select]:border [&_select]:p-2 [&_input]:mt-1 [&_input]:block [&_input]:w-full"><h3 className="font-semibold">Paso 1 — Datos del reporte</h3>
    <label>Definición guardada <select aria-label="Definición guardada" value={seleccion} onChange={(e) => cargarDefinicion(e.target.value)}><option value="">Nueva definición</option>{definiciones.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></label>
    <button type="button" disabled={paginaDefiniciones === 1} onClick={() => void paginaDefinicionesIr(paginaDefiniciones - 1)}>Definiciones anteriores</button><span> Página {paginaDefiniciones} </span><button type="button" disabled={!hayMasDefiniciones} onClick={() => void paginaDefinicionesIr(paginaDefiniciones + 1)}>Más definiciones</button>
    <label>Nombre de definición <input aria-label="Nombre de definición" className="rounded border p-1" value={nombre} onChange={(e) => setNombre(e.target.value)} />{erroresCampo.nombre && <span role="alert">{erroresCampo.nombre}</span>}</label>
    <button type="button" onClick={() => void guardarDefinicion()}>Guardar definición</button>
    {seleccion && <button type="button" onClick={() => void archivarDefinicion()}>Archivar definición</button>}
    <label className="block text-sm">¿Sobre qué información desea generar el reporte?<select className="mt-1 w-full rounded border p-2" value={codigo} onChange={(e) => cambiarFuente(e.target.value)}>{fuentes.map((f) => <option key={f.codigo} value={f.codigo}>{f.etiqueta}</option>)}</select></label>
    </section><section className="space-y-3 rounded-xl border border-slate-200 p-4"><h3 className="font-semibold">Paso 2 — Columnas</h3>
    <fieldset className="mt-3" aria-label="Columnas"><legend className="text-sm font-medium">Columnas seleccionadas: {columnas.length}</legend>{Array.from(new Set(fuente?.columnas.map(c => c.grupo ?? 'Otras columnas') ?? [])).map(titulo => <div key={titulo} className="mt-3"><p className="mb-2 text-sm font-medium">{titulo}</p><div className="flex flex-wrap gap-2">{fuente?.columnas.filter(c => (c.grupo ?? 'Otras columnas') === titulo).map((columna) => <label key={columna.campo} className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"><input type="checkbox" checked={columnas.includes(columna.campo)} onChange={() => { setErrorColumnas(''); setColumnas((actuales) => actuales.includes(columna.campo) ? actuales.filter((c) => c !== columna.campo) : [...actuales, columna.campo].slice(0, 15)) }} />{columna.etiqueta}{columna.sensible && <span className="rounded bg-amber-100 px-1 text-xs">Dato personal</span>}</label>)}</div></div>)}{errorColumnas && <p role="alert" className="text-red-700">{errorColumnas}</p>}</fieldset></section>
    <section className="space-y-3 rounded-xl border border-slate-200 p-4 [&_button]:rounded-lg [&_button]:border [&_button]:px-3 [&_button]:py-2 [&_button]:text-sm [&_button:disabled]:opacity-50 [&_select]:rounded [&_select]:border [&_select]:p-2 [&_input]:rounded [&_input]:border [&_input]:p-2 [&_fieldset]:rounded-lg [&_fieldset]:border [&_fieldset]:p-3"><h3 className="font-semibold">Paso 3 — Filtros y ordenamiento</h3><p className="text-sm">AND: deben cumplirse todas las condiciones. OR: puede cumplirse cualquiera.</p><p className="text-sm text-slate-500">Máximo 10 condiciones y 3 ordenamientos.</p>
    <label>Grupo principal <select aria-label="Operador grupo principal" value={logica} onChange={(e) => setLogica(e.target.value as 'AND' | 'OR')}><option>AND</option><option>OR</option></select></label>
    <button type="button" onClick={() => setGrupos((items) => [...items, { id: crypto.randomUUID(), logica: 'AND' }])}>Añadir grupo</button>
    {grupos.map((grupo, indice) => <div key={grupo.id}>Grupo {indice + 1} <select aria-label={`Operador grupo ${indice + 1}`} value={grupo.logica} onChange={(e) => setGrupos((items) => items.map((item) => item.id === grupo.id ? { ...item, logica: e.target.value as 'AND' | 'OR' } : item))}><option>AND</option><option>OR</option></select> {erroresGrupo[grupo.id] && <span role="alert">{erroresGrupo[grupo.id]}</span>}<button type="button" onClick={() => { setGrupos((items) => items.filter((item) => item.id !== grupo.id)); setCondiciones((items) => items.filter((item) => item.grupo !== grupo.id)) }}>Quitar grupo</button></div>)}
    <label>Límite <input aria-label="Límite" type="number" min={1} max={5000} value={limite} onChange={(e) => setLimite(Number(e.target.value))} />{erroresCampo.limite && <span role="alert">{erroresCampo.limite}</span>}</label>
    <fieldset><legend>Ordenamiento</legend>{orden.map((item, indice) => <div key={item.campo}><select aria-label={`Campo orden ${indice + 1}`} value={item.campo} onChange={(e) => setOrden((xs) => xs.map((x, i) => i === indice ? { ...x, campo: e.target.value } : x))}>{fuente?.ordenables?.map((campo) => <option key={campo} value={campo}>{campo}</option>)}</select><select aria-label={`Dirección orden ${indice + 1}`} value={item.direccion} onChange={(e) => setOrden((xs) => xs.map((x, i) => i === indice ? { ...x, direccion: e.target.value as 'asc' | 'desc' } : x))}><option value="asc">ASC</option><option value="desc">DESC</option></select><button type="button" onClick={() => setOrden((xs) => xs.filter((_, i) => i !== indice))}>Quitar orden</button></div>)}<button type="button" disabled={orden.length >= 3 || !fuente?.ordenables?.length} onClick={() => setOrden((xs) => [...xs, { campo: fuente!.ordenables.find((campo) => !xs.some((x) => x.campo === campo)) ?? fuente!.ordenables[0], direccion: 'asc' }])}>Añadir orden</button></fieldset>
    <div className="mt-3 space-y-2">{condiciones.map((condicion) => { const meta = fuente?.filtros.find((f) => f.campo === condicion.campo); return <div key={condicion.id} className="flex flex-wrap items-start gap-2"><select aria-label="Campo de condición" value={condicion.campo} onChange={(e) => { limpiarError(condicion.id, 'campo'); setCondiciones((xs) => xs.map((x) => x.id === condicion.id ? { ...x, campo: e.target.value, operador: fuente?.filtros.find((f) => f.campo === e.target.value)?.operadores[0] ?? 'eq', valor: '' } : x)) }}>{fuente?.filtros.map((f) => <option key={f.campo} value={f.campo}>{f.etiqueta ?? f.campo}</option>)}</select>{erroresCondicion[condicion.id]?.campo && <span role="alert">{erroresCondicion[condicion.id].campo}</span>}<select aria-label="Operador de condición" value={condicion.operador} onChange={(e) => { limpiarError(condicion.id, 'operador'); setCondiciones((xs) => xs.map((x) => x.id === condicion.id ? { ...x, operador: e.target.value, valor: '' } : x)) }}>{meta?.operadores.filter((o) => o !== 'in' || !['booleano', 'fecha'].includes(meta.control ?? meta.tipo)).map((o) => <option key={o} value={o}>{etiquetasOperador[o] ?? o}</option>)}</select>{erroresCondicion[condicion.id]?.operador && <span role="alert">{erroresCondicion[condicion.id].operador}</span>}{grupos.length > 0 && <select aria-label="Grupo de condición" value={condicion.grupo ?? ''} onChange={(e) => setCondiciones((xs) => xs.map((x) => x.id === condicion.id ? { ...x, grupo: e.target.value || undefined } : x))}><option value="">Principal</option>{grupos.map((g, i) => <option key={g.id} value={g.id}>Grupo {i + 1}</option>)}</select>}{condicion.operador === 'between' ? <div><input aria-label="Valor desde" type={meta?.tipo === 'fecha' ? 'date' : 'number'} value={condicion.valor.split(',')[0] ?? ''} onChange={(e) => setCondiciones((xs) => xs.map((x) => x.id === condicion.id ? { ...x, valor: `${e.target.value},${x.valor.split(',')[1] ?? ''}` } : x))} /><input aria-label="Valor hasta" type={meta?.tipo === 'fecha' ? 'date' : 'number'} value={condicion.valor.split(',')[1] ?? ''} onChange={(e) => setCondiciones((xs) => xs.map((x) => x.id === condicion.id ? { ...x, valor: `${x.valor.split(',')[0] ?? ''},${e.target.value}` } : x))} /></div> : !['isnull', 'notnull'].includes(condicion.operador) && <FilterValueInput key={`${condicion.id}-${condicion.campo}`} filtro={meta} operador={condicion.operador} valor={condicion.valor} error={erroresCondicion[condicion.id]?.valor} onChange={(valor) => { limpiarError(condicion.id, 'valor'); setCondiciones((xs) => xs.map((x) => x.id === condicion.id ? { ...x, valor } : x)) }} />}<button type="button" onClick={() => setCondiciones((xs) => xs.filter((x) => x.id !== condicion.id))}>Quitar</button></div> })}<button type="button" disabled={!fuente || condiciones.length >= 10} onClick={() => setCondiciones((xs) => [...xs, { id: crypto.randomUUID(), campo: fuente!.filtros[0]?.campo ?? '', operador: fuente!.filtros[0]?.operadores[0] ?? 'eq', valor: '' }])}>Añadir condición</button></div>
    {erroresCampo.orden && <p role="alert">{erroresCampo.orden}</p>}</section>
    <section className="space-y-3 rounded-xl border border-slate-200 p-4"><h3 className="font-semibold">Paso 4 — Resultado</h3>
    <div className="mt-3 flex flex-wrap gap-2 [&_button]:rounded-lg [&_button]:border [&_button]:px-3 [&_button]:py-2 [&_button]:text-sm [&_button:disabled]:opacity-50"><button type="button" className="bg-brand-700 text-white" disabled={!codigo || !columnas.length} onClick={() => ejecutar()}><Search className="mr-1 inline h-4 w-4" />Vista previa</button><button type="button" disabled={!codigo || !columnas.length} onClick={() => void previsualizarLibre()}>Vista previa sin guardar</button><button type="button" disabled={!codigo || !columnas.length} onClick={() => ejecutar('CSV')}><Download className="mr-1 inline h-4 w-4" />CSV</button><button type="button" disabled={!codigo || !columnas.length} onClick={() => ejecutar('PDF')}><Download className="mr-1 inline h-4 w-4" />PDF</button></div>
    {!vista && <p className="text-sm text-slate-500">Aún no hay vista previa.</p>}{vista && <div className="mt-4 overflow-auto rounded border border-slate-200 p-3" aria-live="polite">
      <div className="mb-2 flex items-center justify-between gap-3"><p className="text-sm">{vista.cantidad} fila(s){vista.limite_alcanzado ? ' (límite alcanzado)' : ''}</p><button type="button" className="rounded border px-3 py-1 text-sm" onClick={() => { setVista(null); setMensaje('') }}>Limpiar vista previa</button></div>
      <table className="min-w-full text-sm"><thead><tr>{vista.columnas.map((columna) => <th key={columna.campo} className="border p-2 text-left">{columna.etiqueta}</th>)}</tr></thead><tbody>{vista.filas.map((fila, indice) => <tr key={indice}>{fila.map((celda, celdaIndice) => <td key={celdaIndice} className="border p-2">{String(celda ?? '')}</td>)}</tr>)}</tbody></table>
    </div>}</section>
  </section>
}

import axios from 'axios'
import { BookOpenCheck, Link2, Pencil, Plus, UserX, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import type { UnidadEducativa } from '../../app/modelos/Institucion'
import { listarUnidadesCatalogo } from '../../api/catalogosInstitucionales'
import { cargarCatalogoPaginado } from '../../api/catalogosPaginados'
import {
  actualizarMateria, actualizarMateriaCurso, crearMateria, desactivarMateria, desactivarMateriaCurso,
  listarMaterias, listarMateriasCurso, type CursoCatalogo, type EstadoCatalogo, type Materia, type MateriaCurso,
  normalizarColeccion, vincularMateriaCurso,
} from '../../api/materias'
import { Paginacion } from '../auditoria/AuditoriaPage'

const PAGE_SIZE = 20
type Tab = 'materias' | 'curso'

const errorTexto = (error: unknown, fallback: string) => {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 403) return 'No tiene permisos para realizar esta acción.'
    const data = error.response?.data
    if (data && typeof data === 'object') return Object.values(data as Record<string, unknown>).flat().join(' ') || fallback
  }
  return fallback
}
const numero = (value: string) => Number.isInteger(Number(value)) && Number(value) > 0 ? Number(value) : undefined

export default function MateriasPlanEstudioPage() {
  const { user, can } = useAuth()
  const alcance = user?.alcance
  const esDirector = alcance?.tipo === 'COLEGIO'
  const unidadFija = alcance?.tipo === 'UNIDAD' ? alcance.unidad_id : null
  const puedeMaterias = can('materia', 'listar')
  const puedeRelaciones = can('materia-curso', 'listar')
  const [tab, setTab] = useState<Tab>('materias')
  const [unidades, setUnidades] = useState<UnidadEducativa[]>([])
  const [unidad, setUnidad] = useState(unidadFija ? String(unidadFija) : '')
  const [nombre, setNombre] = useState('')
  const [estado, setEstado] = useState('ACTIVO')
  const [paginaMaterias, setPaginaMaterias] = useState(1)
  const [materias, setMaterias] = useState<Materia[]>([])
  const [totalMaterias, setTotalMaterias] = useState(0)
  const [curso, setCurso] = useState('')
  const [materia, setMateria] = useState('')
  const [paginaRelaciones, setPaginaRelaciones] = useState(1)
  const [relaciones, setRelaciones] = useState<MateriaCurso[]>([])
  const [totalRelaciones, setTotalRelaciones] = useState(0)
  const [cursos, setCursos] = useState<CursoCatalogo[]>([])
  const [activas, setActivas] = useState<Materia[]>([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [modalMateria, setModalMateria] = useState<Materia | 'nueva' | null>(null)
  const [modalRelacion, setModalRelacion] = useState<MateriaCurso | 'nueva' | null>(null)
  const [nombreFormulario, setNombreFormulario] = useState('')
  const [enviando, setEnviando] = useState(false)
  const consulta = useRef<AbortController | null>(null)
  const catalogos = useRef<AbortController | null>(null)
  const unidadId = numero(unidad)

  useEffect(() => {
    if (!esDirector || !alcance?.colegio_id || !puedeMaterias) return
    const controller = new AbortController()
    listarUnidadesCatalogo(alcance.colegio_id, controller.signal).then(data => {
      if (!controller.signal.aborted) setUnidades(data)
    }).catch(error => { if (!controller.signal.aborted) setError(errorTexto(error, 'No fue posible cargar las unidades educativas.')) })
    return () => controller.abort()
  }, [alcance?.colegio_id, esDirector, puedeMaterias])

  const cargarMaterias = useCallback(async () => {
    if (!puedeMaterias || !unidadId) { setMaterias([]); setTotalMaterias(0); return }
    consulta.current?.abort(); const controller = new AbortController(); consulta.current = controller
    setCargando(true); setError('')
    try {
      const { data } = await listarMaterias({ unidad_educativa: unidadId, estado: estado as EstadoCatalogo, nombre: nombre.trim(), page: paginaMaterias, page_size: PAGE_SIZE }, controller.signal)
      if (!controller.signal.aborted) { const pagina = normalizarColeccion(data); setMaterias(pagina.results); setTotalMaterias(pagina.count) }
    } catch (error) { if (!controller.signal.aborted && !axios.isCancel(error)) setError(errorTexto(error, 'No fue posible cargar las materias.')) }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }, [nombre, paginaMaterias, puedeMaterias, estado, unidadId])

  const cargarRelaciones = useCallback(async () => {
    if (!puedeRelaciones || !unidadId) { setRelaciones([]); setTotalRelaciones(0); return }
    consulta.current?.abort(); const controller = new AbortController(); consulta.current = controller
    setCargando(true); setError('')
    try {
      const { data } = await listarMateriasCurso({ unidad_educativa: unidadId, curso: numero(curso), materia: numero(materia), estado: estado as EstadoCatalogo, page: paginaRelaciones, page_size: PAGE_SIZE }, controller.signal)
      if (!controller.signal.aborted) { const pagina = normalizarColeccion(data); setRelaciones(pagina.results); setTotalRelaciones(pagina.count) }
    } catch (error) { if (!controller.signal.aborted && !axios.isCancel(error)) setError(errorTexto(error, 'No fue posible cargar las materias por curso.')) }
    finally { if (!controller.signal.aborted) setCargando(false) }
  }, [curso, materia, paginaRelaciones, puedeRelaciones, estado, unidadId])

  // La consulta se sincroniza con la pestaña/filtros y se aborta al reemplazarse.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void (tab === 'materias' ? cargarMaterias() : cargarRelaciones()); return () => consulta.current?.abort() }, [cargarMaterias, cargarRelaciones, tab])

  useEffect(() => {
    catalogos.current?.abort()
    if (!unidadId || !puedeRelaciones) return
    const controller = new AbortController(); catalogos.current = controller
    Promise.all([
      cargarCatalogoPaginado<CursoCatalogo>('/academico/cursos/', { unidad_educativa: unidadId }, controller.signal),
      listarMaterias({ unidad_educativa: unidadId, estado: 'ACTIVO', page: 1, page_size: PAGE_SIZE }, controller.signal),
    ]).then(([cursosUnidad, respuestaMaterias]) => {
      if (!controller.signal.aborted) { setCursos(cursosUnidad); setActivas(normalizarColeccion(respuestaMaterias.data).results) }
    }).catch(error => { if (!controller.signal.aborted) setError(errorTexto(error, 'No fue posible cargar los catálogos de la unidad.')) })
    return () => controller.abort()
  }, [puedeRelaciones, unidadId])

  const cambiarUnidad = (value: string) => { catalogos.current?.abort(); consulta.current?.abort(); setUnidad(value); setPaginaMaterias(1); setPaginaRelaciones(1); setNombre(''); setCurso(''); setMateria(''); setCursos([]); setActivas([]); setRelaciones([]) }
  const abrirMateria = (item: Materia | 'nueva') => { setError(''); setExito(''); setNombreFormulario(item === 'nueva' ? '' : item.nombre); setModalMateria(item) }
  const guardarMateria = async () => {
    const limpio = nombreFormulario.trim().replace(/\s+/g, ' ')
    if (!unidadId || !limpio || enviando) { setError(!unidadId ? 'Seleccione una unidad educativa.' : 'El nombre es obligatorio.'); return }
    setEnviando(true); setError('')
    try {
      if (modalMateria === 'nueva') await crearMateria({ unidad_educativa: unidadId, nombre: limpio })
      else if (modalMateria) await actualizarMateria(modalMateria.id, { nombre: limpio })
      setModalMateria(null); setExito('Materia guardada correctamente.'); await cargarMaterias()
    } catch (error) { setError(errorTexto(error, 'No fue posible guardar la materia.')) }
    finally { setEnviando(false) }
  }
  const desactivarUnaMateria = async (item: Materia) => {
    if (!window.confirm(`¿Desactivar la materia ${item.nombre}?`)) return
    try { await desactivarMateria(item.id); setExito('Materia desactivada.'); await cargarMaterias() } catch (error) { setError(errorTexto(error, 'No fue posible desactivar la materia.')) }
  }
  const abrirRelacion = (item: MateriaCurso | 'nueva') => { setError(''); setExito(''); setModalRelacion(item) }
  const guardarRelacion = async () => {
    const cursoId = numero(curso), materiaId = numero(materia)
    if (!cursoId || !materiaId || enviando) { setError('Seleccione unidad, curso y materia activa.'); return }
    setEnviando(true); setError('')
    try {
      if (modalRelacion === 'nueva') await vincularMateriaCurso({ curso: cursoId, materia: materiaId })
      else if (modalRelacion) await actualizarMateriaCurso(modalRelacion.id, { curso: cursoId, materia: materiaId })
      setModalRelacion(null); setExito('Relación materia–curso guardada.'); await cargarRelaciones()
    } catch (error) { setError(errorTexto(error, 'No fue posible guardar la relación.')) }
    finally { setEnviando(false) }
  }
  const desactivarRelacion = async (item: MateriaCurso) => {
    if (!window.confirm(`¿Desactivar la relación ${item.materia_nombre} – ${item.curso_nombre}?`)) return
    try { await desactivarMateriaCurso(item.id); setExito('Relación desactivada.'); await cargarRelaciones() } catch (error) { setError(errorTexto(error, 'No fue posible desactivar la relación.')) }
  }

  if (!puedeMaterias) return <section className="p-6"><h1 className="text-2xl font-bold">Materias y plan de estudio</h1><p role="alert" className="mt-4 rounded-xl bg-red-50 p-4 text-red-700">No tiene permisos para realizar esta acción.</p></section>
  const puedeCrearMateria = can('materia', 'crear'), puedeEditarMateria = can('materia', 'editar'), puedeDesactivarMateria = can('materia', 'desactivar')
  const puedeCrearRelacion = can('materia-curso', 'crear'), puedeEditarRelacion = can('materia-curso', 'editar'), puedeDesactivarRelacion = can('materia-curso', 'desactivar')
  return <section className="space-y-6 p-4 sm:p-6 lg:p-8" aria-labelledby="materias-title">
    <header className="flex flex-wrap items-center gap-3"><BookOpenCheck className="text-brand-700"/><div><h1 id="materias-title" className="text-2xl font-bold">Materias y plan de estudio</h1><p className="text-sm text-slate-500">Catálogo institucional y materias habilitadas por curso.</p></div></header>
    <div className="flex gap-2 border-b"><button className={tab==='materias'?'border-b-2 border-brand-700 px-3 py-2 font-semibold text-brand-700':'px-3 py-2'} onClick={()=>setTab('materias')}>Catálogo de materias</button>{puedeRelaciones&&<button className={tab==='curso'?'border-b-2 border-brand-700 px-3 py-2 font-semibold text-brand-700':'px-3 py-2'} onClick={()=>setTab('curso')}>Materias por curso</button>}</div>
    <div className="grid gap-3 rounded-2xl bg-white p-4 shadow-sm md:grid-cols-4"><label className="text-sm font-medium">Unidad educativa{esDirector?<select aria-label="Unidad educativa" value={unidad} onChange={e=>cambiarUnidad(e.target.value)} className="mt-1 w-full rounded-lg border p-2"><option value="">Seleccione una unidad</option>{unidades.map(u=><option key={u.id} value={u.id}>{u.nombre}</option>)}</select>:<p className="mt-1 rounded-lg border p-2">{alcance?.unidad_nombre ?? 'Unidad asignada'}</p>}</label><label className="text-sm font-medium">Estado<select aria-label="Estado" value={estado} onChange={e=>{setEstado(e.target.value);setPaginaMaterias(1);setPaginaRelaciones(1)}} className="mt-1 w-full rounded-lg border p-2"><option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option></select></label>{tab==='materias'?<label className="text-sm font-medium">Buscar por nombre<input aria-label="Buscar por nombre" value={nombre} onChange={e=>setNombre(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){setPaginaMaterias(1);void cargarMaterias()}}} className="mt-1 w-full rounded-lg border p-2"/></label>:<><Selector label="Curso" value={curso} onChange={value=>{setCurso(value);setPaginaRelaciones(1)}} options={cursos.map(c=>[String(c.id),c.nombre])}/><Selector label="Materia activa" value={materia} onChange={value=>{setMateria(value);setPaginaRelaciones(1)}} options={activas.map(m=>[String(m.id),m.nombre])}/></>}</div>
    {error&&<p role="alert" className="rounded-xl bg-red-50 p-3 text-red-700">{error} <button className="underline" onClick={()=>void (tab==='materias'?cargarMaterias():cargarRelaciones())}>Reintentar</button></p>}{exito&&<p role="status" className="rounded-xl bg-emerald-50 p-3 text-emerald-700">{exito}</p>}
    {tab==='materias'?<><div className="flex justify-end">{puedeCrearMateria&&<button className="btn-primary" onClick={()=>abrirMateria('nueva')}><Plus size={17}/>Nueva materia</button>}</div><TablaMaterias items={materias} cargando={cargando} puedeEditar={puedeEditarMateria} puedeDesactivar={puedeDesactivarMateria} editar={abrirMateria} desactivar={desactivarUnaMateria}/><Paginacion pagina={paginaMaterias} paginas={Math.max(1,Math.ceil(totalMaterias/PAGE_SIZE))} cambiar={setPaginaMaterias}/></>:<>{!puedeRelaciones?<p className="rounded-xl bg-amber-50 p-4">No tiene permiso para consultar materias por curso.</p>:<><div className="flex justify-end">{puedeCrearRelacion&&<button className="btn-primary" disabled={!unidadId} onClick={()=>abrirRelacion('nueva')}><Link2 size={17}/>Vincular materia</button>}</div><TablaRelaciones items={relaciones} cargando={cargando} puedeEditar={puedeEditarRelacion} puedeDesactivar={puedeDesactivarRelacion} editar={abrirRelacion} desactivar={desactivarRelacion}/><Paginacion pagina={paginaRelaciones} paginas={Math.max(1,Math.ceil(totalRelaciones/PAGE_SIZE))} cambiar={setPaginaRelaciones}/></>}</>}
    {modalMateria&&<Modal title={modalMateria==='nueva'?'Nueva materia':'Editar materia'} close={()=>setModalMateria(null)}>{!unidadId&&<p role="alert" className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Seleccione una unidad educativa antes de guardar la materia.</p>}<label className="text-sm font-medium">Nombre<input aria-label="Nombre de materia" value={nombreFormulario} onChange={e=>setNombreFormulario(e.target.value)} className="mt-1 w-full rounded-lg border p-2" autoFocus/></label><div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={()=>setModalMateria(null)}>Cancelar</button><button className="btn-primary" disabled={enviando||!unidadId} onClick={()=>void guardarMateria()}>{enviando?'Guardando...':'Guardar'}</button></div></Modal>}
    {modalRelacion&&<Modal title={modalRelacion==='nueva'?'Vincular materia al curso':'Editar relación'} close={()=>setModalRelacion(null)}><p className="text-sm text-slate-600">Seleccione el curso y la materia activa en los filtros de esta sección antes de guardar.</p><div className="mt-5 flex justify-end gap-2"><button className="btn-secondary" onClick={()=>setModalRelacion(null)}>Cancelar</button><button className="btn-primary" disabled={enviando||!curso||!materia} onClick={()=>void guardarRelacion()}>{enviando?'Guardando...':'Guardar relación'}</button></div></Modal>}
  </section>
}

function Selector({label,value,onChange,options}:{label:string;value:string;onChange:(value:string)=>void;options:string[][]}) { return <label className="text-sm font-medium">{label}<select aria-label={label} value={value} onChange={e=>onChange(e.target.value)} className="mt-1 w-full rounded-lg border p-2"><option value="">Todos</option>{options.map(([id,text])=><option key={id} value={id}>{text}</option>)}</select></label> }
function Modal({title,close,children}:{title:string;close:()=>void;children:React.ReactNode}) { return <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"><div className="w-full max-w-md rounded-2xl bg-white p-6"><button aria-label="Cerrar formulario" className="float-right" onClick={close}><X size={20}/></button><h2 className="text-xl font-bold">{title}</h2><div className="mt-5">{children}</div></div></div> }
function TablaMaterias({items,cargando,puedeEditar,puedeDesactivar,editar,desactivar}:{items:Materia[];cargando:boolean;puedeEditar:boolean;puedeDesactivar:boolean;editar:(x:Materia)=>void;desactivar:(x:Materia)=>void}) { return <div className="overflow-x-auto rounded-2xl bg-white shadow-sm"><table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr><th className="p-4">Materia</th><th className="p-4">Unidad</th><th className="p-4">Estado</th>{(puedeEditar||puedeDesactivar)&&<th className="p-4">Acciones</th>}</tr></thead><tbody>{cargando?<tr><td className="p-6" colSpan={4}>Cargando materias...</td></tr>:items.length===0?<tr><td className="p-6" colSpan={4}>No se encontraron materias.</td></tr>:items.map(item=><tr key={item.id} className="border-t"><td className="p-4">{item.nombre}</td><td className="p-4">{item.unidad_nombre}</td><td className="p-4">{item.estado}</td>{(puedeEditar||puedeDesactivar)&&<td className="flex gap-3 p-4">{puedeEditar&&<button aria-label={`Editar materia ${item.id}`} onClick={()=>editar(item)}><Pencil size={18}/></button>}{puedeDesactivar&&item.estado==='ACTIVO'&&<button aria-label={`Desactivar materia ${item.id}`} onClick={()=>desactivar(item)} className="text-red-600"><UserX size={18}/></button>}</td>}</tr>)}</tbody></table></div> }
function TablaRelaciones({items,cargando,puedeEditar,puedeDesactivar,editar,desactivar}:{items:MateriaCurso[];cargando:boolean;puedeEditar:boolean;puedeDesactivar:boolean;editar:(x:MateriaCurso)=>void;desactivar:(x:MateriaCurso)=>void}) { return <div className="overflow-x-auto rounded-2xl bg-white shadow-sm"><table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr><th className="p-4">Curso</th><th className="p-4">Materia</th><th className="p-4">Estado</th>{(puedeEditar||puedeDesactivar)&&<th className="p-4">Acciones</th>}</tr></thead><tbody>{cargando?<tr><td className="p-6" colSpan={4}>Cargando relaciones...</td></tr>:items.length===0?<tr><td className="p-6" colSpan={4}>No se encontraron materias por curso.</td></tr>:items.map(item=><tr key={item.id} className="border-t"><td className="p-4">{item.curso_nombre}</td><td className="p-4">{item.materia_nombre}</td><td className="p-4">{item.estado ?? 'ACTIVO'}</td>{(puedeEditar||puedeDesactivar)&&<td className="flex gap-3 p-4">{puedeEditar&&<button aria-label={`Editar relación ${item.id}`} onClick={()=>editar(item)}><Pencil size={18}/></button>}{puedeDesactivar&&(item.estado ?? 'ACTIVO')==='ACTIVO'&&<button aria-label={`Desactivar relación ${item.id}`} onClick={()=>desactivar(item)} className="text-red-600"><UserX size={18}/></button>}</td>}</tr>)}</tbody></table></div> }

import axios from 'axios'
import { BookOpenCheck, Pencil, Plus, Search, UserX, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import { resolveVisualProfile } from '../../app/navigation/navigationConfig'
import type { UnidadEducativa } from '../../app/modelos/Institucion'
import { listarUnidadesCatalogo } from '../../api/catalogosInstitucionales'
import {
  crearAsignacion, desactivarAsignacion, editarAsignacion, listarAsignaciones,
  listarCalendarios, listarCursos, listarMateriasCurso, listarProfesores,
  type AsignacionDocente, type AsignacionPayload, type Calendario, type Curso,
  type MateriaCurso, type Profesor, type TipoAsignacion,
} from '../../api/asignacionesDocentes'
import { Paginacion } from '../auditoria/AuditoriaPage'

const formularioInicial = { calendario_academico: '', tipo: 'MATERIA' as TipoAsignacion, curso: '', profesor: '', materia_curso: '', fecha_inicio: '', fecha_fin: '', horas_semanales: '' }

export default function AsignacionesDocentesPage() {
  const { isProfesor, user, can, puedeComponente, puedeEditarComponente } = useAuth()
  const soloLectura = isProfesor()
  const esSecretaria = resolveVisualProfile(user) === 'SECRETARIA'
  const puedeCrearAsignacion = !soloLectura && (!esSecretaria || (
    can('asignacion-docente', 'crear')
    && puedeComponente('modulo:asignaciones')
    && puedeEditarComponente('modulo:asignaciones')
  ))
  const alcance = user?.alcance
  const esDirector = alcance?.tipo === 'COLEGIO'
  const unidadFija = alcance?.tipo === 'UNIDAD' ? alcance.unidad_id : null
  const [items, setItems] = useState<AsignacionDocente[]>([])
  const [total, setTotal] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [filtros, setFiltros] = useState({ profesor: '', curso: '', materia_curso: '', calendario_academico: '', unidad_educativa: '', tipo: '', estado: '' })
  const [aplicados, setAplicados] = useState(filtros)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [modal, setModal] = useState(false)
  const [editando, setEditando] = useState<AsignacionDocente | null>(null)
  const [form, setForm] = useState(formularioInicial)
  const [errores, setErrores] = useState<Record<string,string>>({})
  const [enviando, setEnviando] = useState(false)
  const [catalogos, setCatalogos] = useState<{ calendarios: Calendario[]; cursos: Curso[]; profesores: Profesor[] }>({ calendarios: [], cursos: [], profesores: [] })
  const [unidades, setUnidades] = useState<UnidadEducativa[]>([])
  const [cargandoCatalogos, setCargandoCatalogos] = useState(false)
  const [materias, setMaterias] = useState<MateriaCurso[]>([])
  const solicitud = useRef<AbortController | null>(null)

  const cargar = useCallback(async () => {
    setCargando(true); setError('')
    solicitud.current?.abort()
    const controlador = new AbortController()
    solicitud.current = controlador
    try {
      const { data } = await listarAsignaciones({
        profesor: numero(aplicados.profesor), curso: numero(aplicados.curso),
        materia_curso: numero(aplicados.materia_curso), calendario_academico: numero(aplicados.calendario_academico),
        unidad_educativa: numero(aplicados.unidad_educativa),
        tipo: aplicados.tipo,
        estado: aplicados.estado,
        page: pagina, page_size: 20,
      }, controlador.signal)
      if (!controlador.signal.aborted) { setItems(data.results); setTotal(data.count) }
    }
    catch (e) {
      const cancelada = controlador.signal.aborted || axios.isCancel(e) || (e instanceof DOMException && e.name === 'AbortError')
      if (!cancelada) {
        const s = axios.isAxiosError(e) ? e.response?.status : undefined
        setError(s === 403 ? 'No tiene permisos para acceder a esta funcionalidad' : s === 400 ? 'Revise los filtros ingresados.' : 'No fue posible cargar las asignaciones.')
      }
    }
    finally { if (!controlador.signal.aborted) setCargando(false) }
  }, [aplicados, pagina])
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar(); return () => solicitud.current?.abort() }, [cargar])

  useEffect(() => {
    if (!esDirector || !alcance?.colegio_id) return
    const controller = new AbortController()
    listarUnidadesCatalogo(alcance.colegio_id, controller.signal)
      .then((resultado) => { if (!controller.signal.aborted) setUnidades(resultado) })
      .catch(() => { if (!controller.signal.aborted) setError('No fue posible cargar las unidades educativas.') })
    return () => controller.abort()
  }, [esDirector, alcance?.colegio_id])

  const unidadSeleccionada = numero(filtros.unidad_educativa) ?? unidadFija ?? undefined
  useEffect(() => {
    if (soloLectura || !unidadSeleccionada) return
    const controller = new AbortController()
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCargandoCatalogos(true)
    Promise.all([listarCalendarios(unidadSeleccionada, controller.signal), listarCursos(unidadSeleccionada, controller.signal), listarProfesores(unidadSeleccionada, controller.signal)])
      .then(([calendarios,cursos,profesores]) => { if (!controller.signal.aborted) setCatalogos({ calendarios,cursos,profesores }) })
      .catch(() => { if (!controller.signal.aborted) setError('No fue posible cargar los catálogos académicos.') })
      .finally(() => { if (!controller.signal.aborted) setCargandoCatalogos(false) })
    return () => controller.abort()
  }, [soloLectura, unidadSeleccionada])

  useEffect(() => {
    if (!form.curso) return
    listarMateriasCurso(Number(form.curso)).then(setMaterias).catch(() => { setMaterias([]); setError('No fue posible cargar las materias del curso.') })
  }, [form.curso])

  const abrir = (asignacion?: AsignacionDocente) => {
    if (!asignacion && !puedeCrearAsignacion) return
    setEditando(asignacion ?? null); setErrores({}); setError(''); setExito('')
    setForm(asignacion ? { calendario_academico: String(asignacion.calendario_academico ?? ''), tipo: asignacion.tipo, curso: String(asignacion.curso), profesor: String(asignacion.profesor), materia_curso: String(asignacion.materia_curso ?? ''), fecha_inicio: asignacion.fecha_inicio, fecha_fin: asignacion.fecha_fin ?? '', horas_semanales: String(asignacion.horas_semanales ?? '') } : formularioInicial)
    setModal(true)
  }
  const validar = () => {
    const e: Record<string,string> = {}
    for (const campo of ['calendario_academico','curso','profesor','fecha_inicio'] as const) if (!form[campo]) e[campo]='Campo obligatorio.'
    if (form.tipo==='MATERIA' && !form.materia_curso) e.materia_curso='Seleccione una materia del curso.'
    if (form.fecha_fin && form.fecha_inicio && form.fecha_fin < form.fecha_inicio) e.fecha_fin='La fecha final no puede ser anterior.'
    if (form.horas_semanales && Number(form.horas_semanales)<=0) e.horas_semanales='Debe ser un número positivo.'
    setErrores(e); return Object.keys(e).length===0
  }
  const guardar = async () => {
    if (enviando || !validar()) return
    setEnviando(true); setError('')
    const payload: AsignacionPayload = { calendario_academico:Number(form.calendario_academico), tipo:form.tipo, curso:Number(form.curso), profesor:Number(form.profesor), materia_curso:form.tipo==='MATERIA'?Number(form.materia_curso):null, fecha_inicio:form.fecha_inicio, fecha_fin:form.fecha_fin||null, horas_semanales:form.horas_semanales?Number(form.horas_semanales):null }
    try { if(editando) await editarAsignacion(editando.id,payload); else await crearAsignacion(payload); setModal(false); setExito(editando?'Asignación actualizada.':'Asignación creada.'); await cargar() }
    catch(e) { const respuesta=axios.isAxiosError(e)?e.response:undefined; const s=respuesta?.status; setError(s===403?'No tiene permiso para realizar esta acción.':s===400?mensajeDominio(respuesta?.data):'No fue posible guardar la asignación.') }
    finally { setEnviando(false) }
  }
  const desactivar = async (a: AsignacionDocente) => {
    if (!window.confirm(`¿Desactivar la asignación de ${a.profesor_nombre}?`)) return
    try { await desactivarAsignacion(a.id); setExito('Asignación desactivada.'); await cargar() } catch(e) { setError(axios.isAxiosError(e)&&e.response?.status===403?'No tiene permiso para desactivar.':'No fue posible desactivar la asignación.') }
  }
  return <section className="p-4 sm:p-6 lg:p-8" aria-labelledby="asignaciones-titulo">
    <header className="mb-6 flex flex-wrap items-center justify-between gap-3"><div><div className="flex items-center gap-3"><BookOpenCheck className="text-brand-700"/><h1 id="asignaciones-titulo" className="text-2xl font-bold">Asignaciones docentes</h1></div><p className="mt-1 text-sm text-slate-500">Carga docente, materias y tutorías por curso.</p></div>{puedeCrearAsignacion&&<button className="btn-primary" onClick={()=>abrir()}><Plus size={18}/>Nueva asignación</button>}</header>
    {!soloLectura&&<form className="mb-5 grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-4" onSubmit={e=>{e.preventDefault();setPagina(1);setAplicados(filtros)}}>
      {esDirector ? <Select label="Unidad educativa" value={filtros.unidad_educativa} onChange={v=>setFiltros({...filtros,unidad_educativa:v,curso:'',profesor:'',calendario_academico:'',materia_curso:''})} opciones={[['','Todas las unidades del colegio'],...unidades.map(u=>[String(u.id),u.nombre])]} /> : unidadFija ? <div className="text-sm font-medium">Unidad educativa<p className="mt-1 rounded-lg border px-3 py-2">{alcance?.unidad_nombre}</p></div> : null}
      <Select label="Profesor" value={filtros.profesor} onChange={v=>setFiltros({...filtros,profesor:v})} opciones={[['','Todos los profesores'],...catalogos.profesores.map(p=>[String(p.id),`${p.usuario?.nombre??''} ${p.usuario?.apellido??''}`.trim()||`Profesor ${p.id}`])]} disabled={!unidadSeleccionada||cargandoCatalogos}/>
      <Select label="Curso" value={filtros.curso} onChange={v=>setFiltros({...filtros,curso:v,materia_curso:''})} opciones={[['','Todos los cursos'],...catalogos.cursos.map(c=>[String(c.id),c.nombre])]} disabled={!unidadSeleccionada||cargandoCatalogos}/>
      <Select label="Calendario académico" value={filtros.calendario_academico} onChange={v=>setFiltros({...filtros,calendario_academico:v})} opciones={[['','Todas las gestiones'],...catalogos.calendarios.map(c=>[String(c.id),`${c.unidad_nombre} - ${c.año}`])]} disabled={!unidadSeleccionada||cargandoCatalogos}/>
      <Select label="Materia del curso" value={filtros.materia_curso} onChange={v=>setFiltros({...filtros,materia_curso:v})} opciones={[['','Todas las materias'],...materias.map(m=>[String(m.id),m.materia_nombre])]} disabled={!filtros.curso}/>
      <Select label="Tipo" value={filtros.tipo} onChange={v=>setFiltros({...filtros,tipo:v})} opciones={[['','Todos'],['MATERIA','Materia'],['TUTOR_CURSO','Tutor de curso']]}/><Select label="Estado" value={filtros.estado} onChange={v=>setFiltros({...filtros,estado:v})} opciones={[['','Todos'],['ACTIVO','Activo'],['INACTIVO','Inactivo']]}/>
      <div className="sm:col-span-2 lg:col-span-4"><button className="btn-primary" type="submit"><Search size={17}/>Consultar</button></div>
    </form>}
    {exito&&<p role="status" className="mb-4 rounded-xl bg-emerald-50 p-3 text-emerald-700">{exito}</p>}{error&&<p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}
    <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">{cargando?<p className="p-8 text-center text-slate-500">Cargando asignaciones...</p>:items.length===0?<p className="p-8 text-center text-slate-500">No se encontraron asignaciones.</p>:<table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr>{['Gestión','Curso','Tipo','Materia','Profesor','Fechas','Estado',...(soloLectura?[]:['Acciones'])].map(x=><th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{items.map(a=><tr key={a.id} className="border-t border-slate-100"><td className="px-4 py-3">{a.gestion_anio??'Histórica'}</td><td className="px-4 py-3">{a.curso_nombre}</td><td className="px-4 py-3">{a.tipo==='MATERIA'?'Materia':'Tutoría'}</td><td className="px-4 py-3">{a.materia_nombre??'—'}</td><td className="px-4 py-3">{a.profesor_nombre}</td><td className="whitespace-nowrap px-4 py-3">{a.fecha_inicio} – {a.fecha_fin??'vigente'}</td><td className="px-4 py-3">{a.estado}</td>{!soloLectura&&<td className="px-4 py-3"><div className="flex gap-2"><button aria-label={`Editar asignación ${a.id}`} onClick={()=>abrir(a)} className="text-brand-700"><Pencil size={18}/></button>{a.estado==='ACTIVO'&&<button aria-label={`Desactivar asignación ${a.id}`} onClick={()=>void desactivar(a)} className="text-red-600"><UserX size={18}/></button>}</div></td>}</tr>)}</tbody></table>}</div>
    <Paginacion pagina={pagina} paginas={Math.max(1,Math.ceil(total/20))} cambiar={setPagina}/>
    {modal&&(editando||puedeCrearAsignacion)&&<div role="dialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/50 p-4"><div className="w-full max-w-2xl rounded-2xl bg-white p-6"><button aria-label="Cerrar formulario" className="float-right" onClick={()=>setModal(false)}><X/></button><h2 className="text-xl font-bold">{editando?'Editar':'Nueva'} asignación</h2><div className="mt-5 grid gap-4 sm:grid-cols-2">
      <Select label="Calendario académico" value={form.calendario_academico} error={errores.calendario_academico} onChange={v=>setForm({...form,calendario_academico:v})} opciones={[['','Seleccione'],...catalogos.calendarios.map(c=>[String(c.id),`${c.unidad_nombre} - ${c.año}`])]}/>
      <Select label="Tipo" value={form.tipo} onChange={v=>setForm({...form,tipo:v as TipoAsignacion,materia_curso:v==='TUTOR_CURSO'?'':form.materia_curso})} opciones={[["MATERIA","Materia"],["TUTOR_CURSO","Tutor de curso"]]}/>
      <Select label="Curso" value={form.curso} error={errores.curso} onChange={v=>setForm({...form,curso:v,materia_curso:''})} opciones={[['','Seleccione'],...catalogos.cursos.map(c=>[String(c.id),c.nombre])]}/>
      <Select label="Profesor" value={form.profesor} error={errores.profesor} onChange={v=>setForm({...form,profesor:v})} opciones={[['','Seleccione'],...catalogos.profesores.map(p=>[String(p.id),`${p.usuario?.nombre??''} ${p.usuario?.apellido??''}`.trim()||`Profesor ${p.id}`])]}/>
      {form.tipo==='MATERIA'&&<Select label="Materia del curso" value={form.materia_curso} error={errores.materia_curso} onChange={v=>setForm({...form,materia_curso:v})} opciones={[['','Seleccione'],...materias.map(m=>[String(m.id),m.materia_nombre])]}/>}<Campo label="Fecha de inicio" type="date" value={form.fecha_inicio} error={errores.fecha_inicio} onChange={v=>setForm({...form,fecha_inicio:v})}/><Campo label="Fecha final" type="date" value={form.fecha_fin} error={errores.fecha_fin} onChange={v=>setForm({...form,fecha_fin:v})}/><Campo label="Horas semanales" type="number" value={form.horas_semanales} error={errores.horas_semanales} onChange={v=>setForm({...form,horas_semanales:v})}/>
      </div><div className="mt-6 flex justify-end gap-2"><button className="btn-secondary" onClick={()=>setModal(false)}>Cancelar</button><button className="btn-primary" disabled={enviando} onClick={()=>void guardar()}>{enviando?'Guardando...':'Guardar'}</button></div></div></div>}
  </section>
}

function Campo({label,value,onChange,type='text',error}:{label:string;value:string;onChange:(v:string)=>void;type?:string;error?:string}) { return <label className="text-sm font-medium">{label}<input aria-label={label} type={type} value={value} onChange={e=>onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"/>{error&&<span className="block text-xs text-red-600">{error}</span>}</label> }
function Select({label,value,onChange,opciones,error,disabled}:{label:string;value:string;onChange:(v:string)=>void;opciones:string[][];error?:string;disabled?:boolean}) { return <label className="text-sm font-medium">{label}<select aria-label={label} aria-busy={disabled} disabled={disabled} value={value} onChange={e=>onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2">{opciones.map(([v,t])=><option key={v} value={v}>{t}</option>)}</select>{error&&<span className="block text-xs text-red-600">{error}</span>}</label> }
function mensajeDominio(data: unknown) { if(!data||typeof data!=='object')return 'Revise los datos ingresados.'; return Object.entries(data as Record<string,unknown>).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join(' '):String(v)}`).join(' ') }
function numero(valor: string) { const resultado = Number(valor); return Number.isInteger(resultado) && resultado > 0 ? resultado : undefined }


import axios from 'axios'
import { Download, FileBarChart } from 'lucide-react'
import { useEffect, useState } from 'react'
import { listarCalendarios, listarCursos, type Calendario, type Curso } from '../../api/asignacionesDocentes'
import { listarPeriodos, type Periodo } from '../../api/evaluacion'
import {
  descargarDocumento, estudiantesDeCurso, generarBoletin, generarCentralizador, listarDocumentos, obtenerDocumentoPdf,
  type DocumentoAcademico, type EstudianteDeCurso,
} from '../../api/reportes'
import ReportesOperativosPanel from './ReportesOperativosPanel'
import QbePanel from './QbePanel'
import HistorialReportes from './HistorialReportes'
import AnaliticaPanel from './AnaliticaPanel'
import { useAuth } from '../../app/contexts/AuthContext'
import { permisosReportes } from '../../app/navigation/reportesPermisos'
import { canEffectivePermission } from '../../app/modelos/Usuarios'

export default function ReportesPage() {
  const { user } = useAuth()
  const permisos = permisosReportes(user)
  const [versionHistorial, setVersionHistorial] = useState(0)
  const pestanas = [
    ...(permisos.operativo ? [{ id: 'operativos', nombre: 'Operativos' }] : []),
    ...(permisos.qbe ? [{ id: 'qbe', nombre: 'Consulta personalizada' }] : []),
    ...(permisos.analitico ? [{ id: 'analitica', nombre: 'Analítica' }, { id: 'voz', nombre: 'Por voz' }] : []),
    ...((permisos.operativo || ((permisos.qbe || permisos.analitico) && canEffectivePermission(user, 'reporte-ejecucion', 'listar'))) ? [{ id: 'historial', nombre: 'Historial' }] : []),
    { id: 'boletines', nombre: 'Boletines' }, { id: 'centralizador', nombre: 'Centralizador' },
  ]
  const [seleccionada, setSeleccionada] = useState('')
  const activa = pestanas.some(p => p.id === seleccionada) ? seleccionada : pestanas[0].id
  const exportado = () => setVersionHistorial(v => v + 1)
  return <section className="p-4 sm:p-6 lg:p-8" aria-labelledby="reportes-titulo">
    <header className="mb-6"><div className="flex items-center gap-3"><FileBarChart className="text-amber-700" /><h1 id="reportes-titulo" className="text-2xl font-bold">Reportes académicos</h1></div><p className="mt-1 text-sm text-slate-500">Reportes operativos, consultas personalizadas, análisis, exportaciones, boletines y centralizadores.</p></header>
    <div role="tablist" aria-label="Secciones de reportes" className="mb-5 flex gap-2 overflow-x-auto border-b border-slate-200" onKeyDown={e => { if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return; e.preventDefault(); const indice = pestanas.findIndex(p => p.id === activa); const siguiente = e.key === 'Home' ? 0 : e.key === 'End' ? pestanas.length - 1 : (indice + (e.key === 'ArrowRight' ? 1 : -1) + pestanas.length) % pestanas.length; setSeleccionada(pestanas[siguiente].id); document.getElementById(`tab-${pestanas[siguiente].id}`)?.focus() }}>
      {pestanas.map(p => <button key={p.id} id={`tab-${p.id}`} role="tab" type="button" aria-selected={activa === p.id} aria-controls={`panel-${p.id}`} tabIndex={activa === p.id ? 0 : -1} onClick={() => setSeleccionada(p.id)} className={`shrink-0 rounded-t px-4 py-2 font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-700 ${activa === p.id ? 'border-b-2 border-brand-700 text-brand-700' : 'text-slate-600'}`}>{p.nombre}</button>)}
    </div>
    <div role="tabpanel" id={`panel-${activa}`} aria-labelledby={`tab-${activa}`}>
      {activa === 'operativos' && <ReportesOperativosPanel onExportado={exportado} />}
      {activa === 'qbe' && <QbePanel onExportado={exportado} />}
      {activa === 'analitica' && <AnaliticaPanel onExportado={exportado} />}
      {activa === 'voz' && <AnaliticaPanel modo="voz" onExportado={exportado} />}
      {activa === 'historial' && <HistorialReportes version={versionHistorial} puedeArchivar={canEffectivePermission(user, 'reporte-definicion', 'archivar')} />}
      {(activa === 'boletines' || activa === 'centralizador') && <DocumentosAcademicos tipo={activa} />}
    </div>
  </section>
}

function DocumentosAcademicos({ tipo }: { tipo: 'boletines' | 'centralizador' }) {
  const [calendarios, setCalendarios] = useState<Calendario[]>([])
  const [cursos, setCursos] = useState<Curso[]>([])
  const [calendarioId, setCalendarioId] = useState('')
  const [cursoId, setCursoId] = useState('')
  const [periodos, setPeriodos] = useState<Periodo[]>([])
  const [periodoId, setPeriodoId] = useState('')
  const [estudiantes, setEstudiantes] = useState<EstudianteDeCurso[]>([])
  const [estudianteId, setEstudianteId] = useState('')
  const [documentos, setDocumentos] = useState<DocumentoAcademico[]>([])
  const [generando, setGenerando] = useState<'boletin' | 'centralizador' | null>(null)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [vistaPdf, setVistaPdf] = useState<string | null>(null)
  const [documentoGenerado, setDocumentoGenerado] = useState<DocumentoAcademico | null>(null)

  useEffect(() => () => { if (vistaPdf) URL.revokeObjectURL(vistaPdf) }, [vistaPdf])

  useEffect(() => {
    listarCalendarios().then(setCalendarios).catch(() => setError('No fue posible cargar las gestiones académicas.'))
    listarCursos().then(setCursos).catch(() => setError('No fue posible cargar los cursos.'))
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPeriodoId('')
    if (!calendarioId) { setPeriodos([]); return }
    listarPeriodos(Number(calendarioId)).then(setPeriodos).catch(() => setError('No fue posible cargar los periodos.'))
  }, [calendarioId])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEstudianteId('')
    if (!cursoId || tipo !== 'boletines') { setEstudiantes([]); return }
    estudiantesDeCurso(Number(cursoId)).then(({ data }) => setEstudiantes(data)).catch(() => setError('No fue posible cargar los estudiantes del curso.'))
  }, [cursoId, tipo])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!cursoId) { setDocumentos([]); return }
    listarDocumentos({ curso: Number(cursoId) }).then(({ data }) => {
      const lista = Array.isArray(data) ? data : data.results
      setDocumentos(lista)
    }).catch(() => setError('No fue posible cargar los documentos emitidos.'))
  }, [cursoId])

  const recargarDocumentos = () => {
    if (!cursoId) return
    listarDocumentos({ curso: Number(cursoId) }).then(({ data }) => setDocumentos(Array.isArray(data) ? data : data.results))
  }

  const manejarError = (e: unknown, mensajePorDefecto: string) => {
    const respuesta = axios.isAxiosError(e) ? e.response : undefined
    if (respuesta?.status === 403) { setError('No tiene permiso para generar reportes de esta unidad educativa.'); return }
    if (respuesta?.status === 400) { setError(mensajeDominio(respuesta.data)); return }
    setError(mensajePorDefecto)
  }

  const crearBoletin = async () => {
    if (!estudianteId || !calendarioId) return
    setGenerando('boletin'); setError(''); setExito('')
    try {
      const estudiante = estudiantes.find((e) => String(e.estudiante) === estudianteId)
      const { data } = await generarBoletin({
        historial_inscripcion: estudiante!.historial_inscripcion,
        calendario_academico: Number(calendarioId),
        periodo: periodoId ? Number(periodoId) : null,
      })
      setDocumentoGenerado(data)
      setVistaPdf(null)
      setExito('Boletín generado correctamente. Puede visualizarlo o descargarlo en PDF.')
      recargarDocumentos()
    } catch (e) { manejarError(e, 'No fue posible generar el boletín.') }
    finally { setGenerando(null) }
  }

  const crearCentralizador = async () => {
    if (!cursoId || !calendarioId) return
    setGenerando('centralizador'); setError(''); setExito('')
    try {
      await generarCentralizador({
        curso: Number(cursoId), calendario_academico: Number(calendarioId),
        periodo: periodoId ? Number(periodoId) : null,
      })
      setExito('Centralizador generado correctamente.')
      recargarDocumentos()
    } catch (e) { manejarError(e, 'No fue posible generar el centralizador.') }
    finally { setGenerando(null) }
  }

  const descargar = async (documento: DocumentoAcademico) => {
    try { await descargarDocumento(documento) }
    catch { setError('No fue posible descargar el documento.') }
  }

  const visualizar = async (documento: DocumentoAcademico) => {
    setError('')
    try { setVistaPdf(URL.createObjectURL(await obtenerDocumentoPdf(documento))) }
    catch { setError('No fue posible visualizar el PDF. Compruebe su permiso de descarga.') }
  }

  return <>
    <div className="mb-5 grid gap-3 rounded-2xl bg-white p-4 shadow-sm sm:grid-cols-3">
      <Select label="Gestión académica" value={calendarioId} onChange={setCalendarioId}
        opciones={[['', 'Seleccione'], ...calendarios.map((c) => [String(c.id), `${c.unidad_nombre} - ${c.año}`])]} />
      <Select label="Curso" value={cursoId} onChange={setCursoId}
        opciones={[['', 'Seleccione'], ...cursos.map((c) => [String(c.id), c.nombre])]} />
      <Select label="Periodo (vacío = anual)" value={periodoId} onChange={setPeriodoId}
        opciones={[['', 'Anual'], ...periodos.map((p) => [String(p.id), p.nombre])]} />
    </div>

    {exito && <p role="status" className="mb-4 rounded-xl bg-emerald-50 p-3 text-emerald-700">{exito}</p>}
    {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}

    {documentoGenerado && <div className="mb-4 flex flex-wrap gap-2">
      <button type="button" className="rounded border bg-white px-3 py-2 text-sm" onClick={() => void visualizar(documentoGenerado)}>Ver boletín PDF</button>
      <button type="button" className="rounded border bg-white px-3 py-2 text-sm" onClick={() => void descargar(documentoGenerado)}>Descargar boletín PDF</button>
    </div>}
    {vistaPdf && <div className="mb-4 rounded-2xl bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3"><h2 className="font-semibold">Vista previa del boletín</h2><button type="button" className="rounded border px-3 py-2 text-sm" onClick={() => setVistaPdf(null)}>Limpiar vista previa</button></div>
      <iframe title="Vista previa del boletín PDF" src={vistaPdf} className="h-[600px] w-full rounded border" />
    </div>}

    <div className="mb-5 grid gap-4 sm:grid-cols-2">
      {tipo === 'boletines' && <div className="rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Boletín individual</h2>
        <div className="mt-3">
          <Select label="Estudiante" value={estudianteId} onChange={setEstudianteId}
            opciones={[['', 'Seleccione'], ...estudiantes.map((e) => [String(e.estudiante), e.estudiante_nombre])]} />
        </div>
        <button className="btn-primary mt-3" disabled={!estudianteId || !calendarioId || generando === 'boletin'} onClick={() => void crearBoletin()}>
          {generando === 'boletin' ? 'Generando...' : 'Generar boletín'}
        </button>
      </div>}
      {tipo === 'centralizador' && <div className="rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Centralizador del curso</h2>
        <p className="mt-1 text-sm text-slate-500">Promedios de todos los estudiantes del curso seleccionado.</p>
        <button className="btn-primary mt-3" disabled={!cursoId || !calendarioId || generando === 'centralizador'} onClick={() => void crearCentralizador()}>
          {generando === 'centralizador' ? 'Generando...' : 'Generar centralizador'}
        </button>
      </div>}
    </div>

    <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50"><tr>{['Tipo', 'Destinatario', 'Periodo', 'Versión', 'Emitido', 'Descarga'].map((x) => <th key={x} className="px-4 py-3">{x}</th>)}</tr></thead>
        <tbody>
          {documentos.length === 0 ? <tr><td colSpan={6} className="p-8 text-center text-slate-500">Seleccione un curso para ver sus documentos.</td></tr> : documentos.map((documento) => <tr key={documento.id} className="border-t border-slate-100">
            <td className="px-4 py-3">{documento.tipo === 'BOLETIN' ? 'Boletín' : 'Centralizador'}</td>
            <td className="px-4 py-3">{documento.estudiante_nombre ?? documento.curso_nombre ?? '—'}</td>
            <td className="px-4 py-3">{documento.periodo_nombre ?? 'Anual'}</td>
            <td className="px-4 py-3">v{documento.version}</td>
            <td className="px-4 py-3">{new Date(documento.emitido_at).toLocaleString()}</td>
            <td className="px-4 py-3"><div className="flex items-center gap-3"><button type="button" className="text-brand-700 underline" onClick={() => void visualizar(documento)}>Ver PDF</button><button aria-label={`Descargar documento ${documento.id}`} className="text-brand-700" onClick={() => void descargar(documento)}><Download size={18} /></button></div></td>
          </tr>)}
        </tbody>
      </table>
    </div>
  </>
}

function Select({ label, value, onChange, opciones }: { label: string; value: string; onChange: (v: string) => void; opciones: string[][] }) {
  return <label className="text-sm font-medium">{label}<select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2">{opciones.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
}
function mensajeDominio(data: unknown) {
  if (!data || typeof data !== 'object') return 'Revise los datos ingresados.'
  return Object.entries(data as Record<string, unknown>).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : String(v)}`).join(' ')
}

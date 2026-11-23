import { obtenerPanelDirector, type FiltrosDirector, type PanelDirector } from '../../api/portal'
import { useAuth } from '../../app/contexts/AuthContext'
import { DashboardSection } from '../dashboard/components/DashboardComponents'
import { CalendarFilters, PortalMetric, PortalSelect, PortalStatus, UpdatedAt } from './PortalUI'
import { usePortal } from './usePortal'

export default function PanelInstitucional() {
  const { user } = useAuth()
  return <DirectorPanel key={`${user?.id}:${user?.alcance?.colegio_id}:${user?.alcance?.unidad_id}`} />
}
function DirectorPanel() {
  const { data, loading, error, select, reload } = usePortal<PanelDirector, FiltrosDirector>(obtenerPanelDirector)
  const unit = data?.unidad_seleccionada ?? undefined, calendar = data?.gestion?.id
  const period = data?.periodos.find(row => row.id === data.periodo)?.nombre ?? 'Toda la gestión'
  return <section aria-labelledby="panel-institucional-title" className="mx-auto max-w-7xl space-y-6 px-4 py-7 sm:px-6 lg:px-8"><header className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-widest text-brand-700">Dirección académica</p><h1 id="panel-institucional-title" className="mt-2 text-3xl font-bold">Panel institucional</h1><p className="mt-2 text-slate-600">Indicadores agregados del colegio y sus unidades educativas.</p></div><button type="button" className="btn-secondary" onClick={reload} disabled={loading}>Actualizar panel</button></header>
    <PortalStatus loading={loading} error={error} retry={reload} title="panel institucional" />
    {data && <><div className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-3"><PortalSelect label="Unidad educativa" value={unit ?? ''} onChange={id => select(id ? { unidad_educativa: id } : {})}><option value="">Todo el colegio</option>{data.unidades.map(row => <option key={row.id} value={row.id}>{row.nombre}</option>)}</PortalSelect><CalendarFilters gestiones={data.gestiones} gestion={calendar ?? ''} periodos={data.periodos} periodo={data.periodo ?? ''} onGestion={id => select({ unidad_educativa: unit, calendario_academico: id })} onPeriodo={id => select({ unidad_educativa: unit, calendario_academico: calendar, ...(id ? { periodo: id } : {}) })} /></div>
      <p className="text-sm font-semibold text-brand-800">Alcance: {data.unidades.find(row => row.id === unit)?.nombre ?? 'Todo el colegio'}{data.gestion ? ` · Gestión ${data.gestion.anio} · ${period}` : ''}</p>
      <DashboardSection title="Situación actual" description="Contadores actuales del ámbito seleccionado; no cambian con el periodo académico."><div className="grid gap-4 sm:grid-cols-3"><PortalMetric title="Estudiantes activos" value={data.indicadores.estudiantes_activos} /><PortalMetric title="Docentes activos" value={data.indicadores.docentes_activos} /><PortalMetric title="Cursos" value={data.indicadores.cursos} /></div></DashboardSection>
      <DashboardSection title="Resultados académicos del filtro" description={data.gestion ? `Gestión ${data.gestion.anio} · ${period}` : 'Seleccione una unidad y una gestión para consultar indicadores académicos.'}><div className="grid gap-4 sm:grid-cols-3"><PortalMetric title="Promedio académico" value={data.indicadores.promedio} /><PortalMetric title="Aprobación" value={data.indicadores.porcentaje_aprobacion} suffix="%" /><PortalMetric title="Asistencia" value={data.indicadores.porcentaje_asistencia} suffix="%" /></div></DashboardSection>
      <DashboardSection title="Comunicación institucional" description="Comunicados publicados y lectura de sus destinatarios en el ámbito y filtro seleccionados."><div className="grid gap-4 sm:grid-cols-2"><PortalMetric title="Comunicados publicados" value={data.indicadores.comunicados_publicados} /><PortalMetric title="Lectura de comunicados" value={data.indicadores.porcentaje_lectura} suffix="%" /></div></DashboardSection><UpdatedAt date={data.actualizado_at} />
    </>}
  </section>
}

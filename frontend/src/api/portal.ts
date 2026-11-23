import api from './axiosInstance'

export interface GestionPortal { id: number; anio: number; activo: boolean }
export interface PeriodoPortal { id: number; nombre: string; estado: string }
export interface EstudiantePortal { id: number; nombre: string; curso: string | null; unidad_educativa: number; unidad_nombre: string }
export interface BoletinPortal { id: number; tipo: string; periodo: string | null; version: number; created_at: string; descarga_url: string }
export interface FiltrosFamilia { estudiante?: number; calendario_academico?: number; periodo?: number }
export interface FiltrosDirector { unidad_educativa?: number; calendario_academico?: number; periodo?: number }
interface CalendarioPortal { gestiones: GestionPortal[]; gestion: GestionPortal | null; periodos: PeriodoPortal[]; periodo: number | null; actualizado_at: string }
export interface PortalFamilia extends CalendarioPortal {
  estudiantes: EstudiantePortal[]; seleccionado: number | null; estudiante: EstudiantePortal | null
  notas: { materia: string; periodos: { id: number; nombre: string; nota: string; condicion: string }[]; anual: { nota: string; condicion: string } | null }[]
  horarios: { id: number; dia: number; hora_inicio: string; hora_fin: string; materia: string; docente: string; aula: string }[]
  asistencia: { fuente: 'SESIONES' | 'LEGACY' | 'SIN_DATOS'; total: number; presentes: number; faltas: number; atrasos: number; licencias: number; porcentaje: number | null; registros: { id: number; fecha: string; estado: string; materia: string }[] }
  boletines: BoletinPortal[]
  comunicados: { id: number; titulo: string; prioridad: string; leido_at: string | null; publicado_at: string | null }[]
  notificaciones: { no_leidas: number; recientes: { id: number; tipo: string; titulo: string; created_at: string; leida_at: string | null; comunicado: number | null }[] }
  pagos: { disponible: false; mensaje: string }
}
export interface PanelDirector extends CalendarioPortal {
  unidades: { id: number; nombre: string }[]; unidad_seleccionada: number | null
  indicadores: { estudiantes_activos: number; docentes_activos: number; cursos: number; promedio: number | null; porcentaje_aprobacion: number | null; porcentaje_asistencia: number | null; comunicados_publicados: number; porcentaje_lectura: number | null }
  alcance: { colegio_id: number; unidad_id: number | null }
}
export const obtenerPortalFamiliar = (params: FiltrosFamilia = {}, signal?: AbortSignal) => api.get<PortalFamilia>('/portal/familia/', { params, signal })
export const obtenerPanelDirector = (params: FiltrosDirector = {}, signal?: AbortSignal) => api.get<PanelDirector>('/portal/panel-director/', { params, signal })
// El identificador se resuelve exclusivamente contra el endpoint privado existente.
export const obtenerBoletin = async (id: number, signal?: AbortSignal): Promise<Blob> => {
  const { data } = await api.get<Blob>(`/estudiantes/documentos-academicos/${id}/descargar/`, { responseType: 'blob', signal })
  return data
}

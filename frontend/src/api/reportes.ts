import axiosInstance from './axiosInstance'
import type { PaginatedResponse } from './types'

export interface FiltrosAnalitica { unidad_educativa: number; calendario_academico: number; periodo?: number; curso?: number; materia?: number }
export interface ResumenAnalitica {
  contexto: Record<string, number | null>
  indicadores: Record<string, number | null>
  series: Record<string, Array<{ etiqueta: string; valor: number }> | null>
  metadatos: { errores_parciales: Array<{ componente: string; mensaje: string }>; matricula_actual: { tipo_temporal: string; advertencia: string; filtros_aplicados: string[]; filtros_no_aplicables: string[] }; metricas_omitidas: string[]; incidentes: { advertencia: string; filtros_no_aplicables: string[] } }
}
export const resumenAnalitica = (params: FiltrosAnalitica, signal?: AbortSignal) => axiosInstance.get<ResumenAnalitica>('/reportes/analitica/resumen/', { params, signal })
export const exportarAnalitica = (filtros: FiltrosAnalitica, formato: 'CSV' | 'PDF', signal?: AbortSignal) => axiosInstance.post('/reportes/analitica/exportar/', { filtros, formato }, { responseType: 'blob', signal })

export interface InterpretacionVoz { estado: 'LISTO' | 'AMBIGUO' | 'FALTAN_DATOS' | 'NO_SOPORTADO'; intencion?: string; formato?: 'VISTA' | 'CSV' | 'PDF'; colegio?: number; filtros?: Record<string, number | null>; token_interpretacion?: string; advertencias?: string[]; faltantes?: string[]; opciones?: Array<{ id: number; nombre: string }> }
export interface ResultadoVozEstudiantes { tipo: 'ESTUDIANTES_INSCRITOS'; columnas: string[]; filas: string[][]; limite: number; hay_mas: boolean }
export type ResultadoVoz = ResumenAnalitica | ResultadoVozEstudiantes
export const interpretarVoz = (texto: string, contexto: Partial<FiltrosAnalitica>) => axiosInstance.post<InterpretacionVoz>('/reportes/voz/interpretar/', { texto, contexto })
export const ejecutarVoz = (token_interpretacion: string, formato: 'VISTA' | 'CSV' | 'PDF') => axiosInstance.post<ResultadoVoz | Blob>('/reportes/voz/ejecutar/', { token_interpretacion, confirmacion: true }, { responseType: formato === 'VISTA' ? 'json' : 'blob' })

export interface ColumnaReporteOperativo { campo: string; etiqueta: string; tipo: string; sensible?: boolean; seleccionada_por_defecto?: boolean; grupo?: string }
export interface FiltroReporteOperativo { campo: string; tipo: string; operadores: string[]; etiqueta?: string; control?: string; depende_de?: string; opciones?: Array<{ valor: string; etiqueta: string }> }
export interface FuenteReporteOperativo {
  codigo: string; nombre: string; descripcion: string; version: number
  columnas: ColumnaReporteOperativo[]; predeterminadas: string[]
  filtros: FiltroReporteOperativo[]; ordenables: string[]; limite: number
}
export interface DefinicionReporteOperativo {
  id: number; nombre: string; codigo_fuente: string; especificacion: EspecificacionReporteOperativo
}
export interface EspecificacionReporteOperativo {
  columnas: string[]
  filtros: Array<{ campo: string; operador: string; valor: string | number | boolean | Array<string | number | boolean> }>
  orden: Array<{ campo: string; direccion: 'asc' | 'desc' }>
}
export interface VistaPreviaReporte { columnas: Array<{ campo: string; etiqueta: string }>; filas: unknown[][]; cantidad: number; limite_alcanzado: boolean }

export const catalogoReportesOperativos = () => axiosInstance.get<PaginatedResponse<FuenteReporteOperativo>>('/reportes/catalogo/')
export const definicionesReportesOperativos = () => axiosInstance.get<PaginatedResponse<DefinicionReporteOperativo>>('/reportes/definiciones/')
export const crearDefinicionReporteOperativo = (payload: { nombre: string; codigo_fuente: string; especificacion: EspecificacionReporteOperativo }) =>
  axiosInstance.post<DefinicionReporteOperativo>('/reportes/definiciones/', payload)
export const actualizarDefinicionReporteOperativo = (id: number, especificacion: EspecificacionReporteOperativo) =>
  axiosInstance.patch<DefinicionReporteOperativo>(`/reportes/definiciones/${id}/`, { especificacion })
export const previsualizarReporteOperativo = (definicion_id: number) =>
  axiosInstance.post<VistaPreviaReporte>('/reportes/previsualizar/', { definicion_id })
export const exportarReporteOperativo = (definicion_id: number, formato: 'CSV' | 'PDF') =>
  axiosInstance.post('/reportes/exportar/', { definicion_id, formato }, { responseType: 'blob' })

export interface FuenteQbe { codigo: string; etiqueta: string; columnas: ColumnaReporteOperativo[]; filtros: FiltroReporteOperativo[]; ordenables: string[]; predeterminadas?: string[] }
export interface EspecificacionQbe { columnas: string[]; condiciones: unknown; orden: Array<{ campo: string; direccion: 'asc' | 'desc' }>; limite?: number }
export const catalogoQbe = () => axiosInstance.get<PaginatedResponse<FuenteQbe>>('/reportes/qbe/catalogo/')
export const crearDefinicionQbe = (payload: { nombre: string; codigo_fuente: string; especificacion: EspecificacionQbe }) => axiosInstance.post<DefinicionReporteOperativo>('/reportes/qbe/definiciones/', payload)
export const definicionesQbe = (page?: number) => axiosInstance.get<PaginatedResponse<DefinicionReporteOperativo>>('/reportes/qbe/definiciones/', { params: page ? { page } : undefined })
export const actualizarDefinicionQbe = (id: number, especificacion: EspecificacionQbe) => axiosInstance.patch<DefinicionReporteOperativo>(`/reportes/qbe/definiciones/${id}/`, { especificacion })
export const guardarNombreQbe = (id: number, nombre: string, especificacion: EspecificacionQbe) => axiosInstance.patch<DefinicionReporteOperativo>(`/reportes/qbe/definiciones/${id}/`, { nombre, especificacion })
export const archivarDefinicionQbe = (id: number) => axiosInstance.post(`/reportes/qbe/definiciones/${id}/archivar/`, {})
export const previsualizarQbeLibre = (codigo_fuente: string, especificacion: EspecificacionQbe, signal?: AbortSignal) => axiosInstance.post<VistaPreviaReporte>('/reportes/qbe/previsualizar/', { codigo_fuente, especificacion }, { signal })
export const previsualizarQbe = (definicion_id: number, signal?: AbortSignal) => axiosInstance.post<VistaPreviaReporte>('/reportes/qbe/previsualizar/', { definicion_id }, { signal })
export const exportarQbe = (definicion_id: number, formato: 'CSV' | 'PDF') => axiosInstance.post('/reportes/qbe/exportar/', { definicion_id, formato }, { responseType: 'blob' })

export interface EjecucionReporte {
  id: string; nombre: string; fuente: string; fuente_nombre?: string; tipo: string; formato: string; estado: string
  unidad: string | null; unidad_id: number | null; ejecutor: string | null
  iniciada_at: string; finalizada_at: string | null; tamano: number | null; archivado_at: string | null
}
export const listarEjecuciones = (params: Record<string, string | number>) => axiosInstance.get<PaginatedResponse<EjecucionReporte>>('/reportes/ejecuciones/', { params })
export const detalleEjecucion = (id: string) => axiosInstance.get<EjecucionReporte>(`/reportes/ejecuciones/${id}/`)
export const archivarEjecucion = (id: string) => axiosInstance.post(`/reportes/ejecuciones/${id}/archivar/`, {})
export const descargarEjecucion = async (item: EjecucionReporte) => {
  const { data } = await axiosInstance.get(`/reportes/ejecuciones/${item.id}/descargar/`, { responseType: 'blob' })
  const url = URL.createObjectURL(data as Blob)
  const enlace = document.createElement('a')
  enlace.href = url; enlace.download = `reporte-${item.id}.${item.formato.toLowerCase()}`; enlace.click(); URL.revokeObjectURL(url)
}

export type TipoDocumento = 'BOLETIN' | 'CENTRALIZADOR'

export interface DocumentoAcademico {
  id: number
  tipo: TipoDocumento
  historial_inscripcion: number | null
  estudiante_nombre: string | null
  curso: number | null
  curso_nombre: string | null
  periodo: number | null
  periodo_nombre: string | null
  calendario_academico: number
  gestion_anio: number | null
  version: number
  archivo_mime: string
  archivo_tamano: number
  emisor_snapshot: string | null
  emitido_at: string
  descarga_url: string
}

export interface EstudianteDeCurso { estudiante: number; estudiante_nombre: string; historial_inscripcion: number }

export interface GenerarBoletinPayload {
  historial_inscripcion: number
  calendario_academico: number
  periodo?: number | null
}
export interface GenerarCentralizadorPayload {
  curso: number
  calendario_academico: number
  periodo?: number | null
}

export const listarDocumentos = (params: { curso?: number; tipo?: TipoDocumento; calendario_academico?: number } = {}) =>
  axiosInstance.get<PaginatedResponse<DocumentoAcademico> | DocumentoAcademico[]>(
    '/estudiantes/documentos-academicos/', { params },
  )

export const generarBoletin = (payload: GenerarBoletinPayload) =>
  axiosInstance.post<DocumentoAcademico>('/estudiantes/documentos-academicos/generar-boletin/', payload)

export const generarCentralizador = (payload: GenerarCentralizadorPayload) =>
  axiosInstance.post<DocumentoAcademico>('/estudiantes/documentos-academicos/generar-centralizador/', payload)

export const estudiantesDeCurso = (curso: number) =>
  axiosInstance.get<EstudianteDeCurso[]>('/estudiantes/documentos-academicos/estudiantes-curso/', { params: { curso } })

export const obtenerDocumentoPdf = async (documento: DocumentoAcademico): Promise<Blob> => {
  const baseUrl = String(axiosInstance.defaults.baseURL ?? '/api')
  const prefijoApi = new URL(baseUrl, window.location.origin).pathname.replace(/\/$/, '')
  const urlDocumento = new URL(documento.descarga_url, window.location.origin)
  const rutaCompleta = `${urlDocumento.pathname}${urlDocumento.search}`
  const ruta = prefijoApi && rutaCompleta.startsWith(`${prefijoApi}/`)
    ? rutaCompleta.slice(prefijoApi.length)
    : rutaCompleta
  const { data } = await axiosInstance.get(ruta, { responseType: 'blob' })
  return data as Blob
}

export const descargarDocumento = async (documento: DocumentoAcademico) => {
  const url = URL.createObjectURL(await obtenerDocumentoPdf(documento))
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = `${documento.tipo.toLowerCase()}_${documento.id}_v${documento.version}.pdf`
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
}

import axiosInstance from './axiosInstance'

export interface InscripcionDisciplina { id:number; estudiante:number; estudiante_nombre:string; curso_nombre:string; fecha_inscripcion:string }
export interface TutorDisciplina { id:number; nombre:string; es_principal:boolean }
export interface Incidente { id:number; historial_inscripcion:number; fecha:string; tipo:string; severidad:string; descripcion:string; estado:string; created_by:number; responsable_nombre:string; estudiante_nombre:string; curso_nombre:string }
export interface Citacion { id:number; incidente:number; tutor_estudiante:number; fecha_programada:string; descripcion:string|null; resultado:string|null; estado:string; tutor_nombre:string; responsable_nombre:string }
export interface CalificacionCorregible { id:number; valor:string; puntaje_maximo:string; estudiante_nombre:string; actividad_nombre:string; curso_nombre:string; materia_nombre:string; periodo_nombre:string }
export interface Correccion { id:number; calificacion:number; valor_anterior:string; valor_nuevo:string; motivo:string; estado:string; solicitado_por:number|null; autorizado_por:number|null; solicitante_nombre:string; autorizador_nombre:string; solicitado_at:string; resuelto_at:string|null; detalle_calificacion:CalificacionCorregible }
export interface IncidentePayload { historial_inscripcion:number; fecha:string; tipo:string; severidad:string; descripcion:string; estado?:string }
export interface CitacionPayload { incidente:number; tutor_estudiante:number; fecha_programada:string; descripcion:string }

export const guardarIncidente = (payload:IncidentePayload, id?:number) => id
  ? axiosInstance.patch<Incidente>(`/estudiantes/incidentes/${id}/`,payload)
  : axiosInstance.post<Incidente>('/estudiantes/incidentes/',payload)
export const guardarCitacion = (payload:CitacionPayload, id?:number) => id
  ? axiosInstance.patch<Citacion>(`/estudiantes/citaciones/${id}/`,payload)
  : axiosInstance.post<Citacion>('/estudiantes/citaciones/',payload)
export const cambiarEstadoCitacion = (id:number,estado:string) => axiosInstance.post<Citacion>(`/estudiantes/citaciones/${id}/estado/`,{estado})
export const solicitarCorreccion = (payload:{calificacion:number;valor_nuevo:string;motivo:string}) => axiosInstance.post<Correccion>('/academico/correcciones/',payload)
export const resolverCorreccion = (id:number, aprobar:boolean) => axiosInstance.post<Correccion>(`/academico/correcciones/${id}/${aprobar?'aprobar':'rechazar'}/`)

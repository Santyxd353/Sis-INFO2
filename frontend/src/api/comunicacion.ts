import api from './axiosInstance'

export interface Comunicado {
  id: number
  titulo: string
  cuerpo: string
  unidad_educativa: number
  curso: number | null
  prioridad: 'NORMAL' | 'URGENTE'
  requiere_confirmacion: boolean
  estado: 'BORRADOR' | 'PUBLICADO' | 'ARCHIVADO'
  created_at: string
  publicado_at: string | null
  leido_at: string | null
  puede_gestionar: boolean
  es_destinatario: boolean
  estadisticas: null | { destinatarios: number; leidos: number; porcentaje_lectura: number }
}
export type ComunicadoPayload = Pick<Comunicado, 'titulo' | 'cuerpo' | 'unidad_educativa' | 'curso' | 'prioridad' | 'requiere_confirmacion'>
export const CATEGORIAS = {
  COMUNICADO: 'Comunicados', FALTA: 'Faltas', ATRASO: 'Atrasos', NOTA_BAJA: 'Notas bajas',
  PAGO: 'Pagos', CONTINGENCIA: 'Contingencias', CITACION: 'Citaciones', BOLETIN: 'Boletines',
} as const
export type Categoria = keyof typeof CATEGORIAS
export type Preferencias = Record<Categoria, boolean>
export interface Notificacion {
  id: number
  tipo: Categoria
  titulo: string
  cuerpo: string
  created_at: string
  leida_at: string | null
  comunicado: number | null
  datos: Record<string, unknown>
}
export interface AlertaPayload { estudiante: number; tipo: 'PAGO' | 'CONTINGENCIA'; titulo: string; cuerpo: string; clave_evento: string }
export const crearComunicado = (payload: ComunicadoPayload) => api.post<Comunicado>('/comunicacion/comunicados/', payload)
export const actualizarComunicado = (id: number, payload: Partial<ComunicadoPayload>) => api.patch<Comunicado>(`/comunicacion/comunicados/${id}/`, payload)
export const publicarComunicado = (id: number) => api.post<Comunicado>(`/comunicacion/comunicados/${id}/publicar/`)
export const archivarComunicado = (id: number) => api.post<Comunicado>(`/comunicacion/comunicados/${id}/archivar/`)
export const confirmarLectura = (id: number) => api.post<Comunicado>(`/comunicacion/comunicados/${id}/leer/`)
export const leerNotificacion = (id: number) => api.post<Notificacion>(`/comunicacion/notificaciones/${id}/leer/`)
export const guardarPreferencias = (payload: Partial<Preferencias>) => api.patch<Preferencias>('/comunicacion/preferencias/', payload)
export const emitirAlerta = (payload: AlertaPayload) => api.post<{ creadas: number }>('/comunicacion/alertas/', payload)

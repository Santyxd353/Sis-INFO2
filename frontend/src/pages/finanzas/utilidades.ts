import axios from 'axios'

export const PAGE_SIZE = 20

export interface ContextoFinanzas {
  unidadId: number
  calendarioId: number | undefined
}

export const errorTexto = (error: unknown, fallback: string) => {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 403) return 'No tiene permisos para realizar esta acción.'
    const data = error.response?.data
    if (data && typeof data === 'object') return Object.values(data as Record<string, unknown>).flat().join(' ') || fallback
  }
  return fallback
}

export const NIVELES: [string, string][] = [['INI', 'Inicial'], ['PRI', 'Primaria'], ['SEC', 'Secundaria']]

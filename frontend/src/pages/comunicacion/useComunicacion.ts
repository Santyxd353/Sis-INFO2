import { useEffect, useState } from 'react'
import api from '../../api/axiosInstance'
import { cargarCatalogoPaginado } from '../../api/catalogosPaginados'
import { useAuth } from '../../app/contexts/AuthContext'
import { resolveVisualProfile } from '../../app/navigation/navigationConfig'
import { errorFields } from '../workflows/useWorkflow'

export function useGestorComunicacion() {
  const { user, can } = useAuth()
  return resolveVisualProfile(user) === 'DIRECTOR' && ['COLEGIO', 'UNIDAD'].includes(user?.alcance?.tipo ?? '') && Boolean(user?.alcance?.colegio_id) && can('comunicacion', 'gestionar')
}

export function useRecurso<T>(url: string, revision = 0, enabled = true) {
  const key = `${url}|${revision}`
  const [state, setState] = useState<{ key: string; data?: T; error?: string }>({ key: '' })
  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    api.get<T>(url, { signal: controller.signal }).then(({ data }) => {
      if (!controller.signal.aborted) setState({ key, data })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setState({ key, error: Object.values(errorFields(error)).join(' ') })
    })
    return () => controller.abort()
  }, [url, key, enabled])
  const current = enabled && state.key === key ? state : undefined
  return { data: current?.data, error: current?.error ?? '', loading: enabled && !current }
}

export function useCatalogo<T extends { id: number }>(url: string, params: Record<string, string | number>, enabled = true) {
  const query = JSON.stringify(params)
  const [revision, setRevision] = useState(0)
  const key = `${url}|${query}|${revision}`
  const [state, setState] = useState<{ key: string; items?: T[]; error?: string }>({ key: '' })
  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    cargarCatalogoPaginado<T>(url, JSON.parse(query), controller.signal).then(items => {
      if (!controller.signal.aborted) setState({ key, items })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setState({ key, error: Object.values(errorFields(error)).join(' ') })
    })
    return () => controller.abort()
  }, [url, query, key, enabled])
  const current = enabled && state.key === key ? state : undefined
  return { items: current?.items ?? [], error: current?.error ?? '', loading: enabled && !current, retry: () => setRevision(v => v + 1) }
}

export function fechaComunicacion(value: string) {
  return new Date(value).toLocaleString('es-BO', { dateStyle: 'medium', timeStyle: 'short' })
}

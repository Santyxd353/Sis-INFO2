import axios from 'axios'
import { useEffect, useRef, useState } from 'react'

export function usePortal<T, F extends object>(load: (filters: F, signal: AbortSignal) => Promise<{ data: T }>) {
  const [filters, setFilters] = useState<F>({} as F)
  const [result, setResult] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true })
  const pending = useRef<AbortController | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    pending.current = controller
    void load(filters, controller.signal).then(({ data }) => {
      if (!controller.signal.aborted) setResult({ data, error: null, loading: false })
    }).catch(error => {
      if (controller.signal.aborted || axios.isCancel(error)) return
      const status = axios.isAxiosError(error) ? error.response?.status : undefined
      const message = status === 404 ? 'No se encontró información autorizada para esta selección.' : status === 403 ? 'No tiene permiso para consultar este portal.' : 'No se pudo cargar la información. Intente nuevamente.'
      setResult({ data: null, error: message, loading: false })
    })
    return () => controller.abort()
  }, [load, filters])
  function select(next: F) {
    pending.current?.abort()
    setResult({ data: null, error: null, loading: true })
    setFilters(next)
  }
  return { ...result, select, reload: () => select({ ...filters }) }
}

import axiosInstance from './axiosInstance'
import type { AxiosResponse } from 'axios'
import type { PaginatedResponse } from './types'

export type CatalogoParametro = string | number | boolean | null | undefined
export type CatalogoParametros = Record<string, CatalogoParametro>

type ConId = { id: number }

const parametrosValidos = (params?: CatalogoParametros) => Object.fromEntries(
  Object.entries(params ?? {}).filter(([, value]) => value !== undefined && value !== null && value !== ''),
)

const rutaSiguienteSegura = (next: string) => {
  const url = new URL(next, window.location.origin)
  const baseUrl = String(axiosInstance.defaults.baseURL ?? '/api')
  const apiUrl = new URL(baseUrl, window.location.origin)
  const prefijoApi = apiUrl.pathname.replace(/\/$/, '')
  const perteneceAlApi = !prefijoApi || url.pathname === prefijoApi || url.pathname.startsWith(`${prefijoApi}/`)
  const usaProxyRelativo = !/^https?:\/\//i.test(baseUrl)
  const origenPermitido = url.origin === window.location.origin || url.origin === apiUrl.origin

  // Django puede construir `next` con el host interno del proxy de desarrollo.
  // En ese caso se conserva solo la ruta bajo /api y Axios vuelve a usar su baseURL.
  if (!origenPermitido && !(usaProxyRelativo && perteneceAlApi)) {
    throw new Error('El catálogo devolvió una página de otro origen.')
  }
  return `${url.pathname}${url.search}`
}

/** Recupera únicamente catálogos pequeños; nunca listados principales paginados. */
export async function cargarCatalogoPaginado<T extends ConId>(
  endpoint: string,
  params?: CatalogoParametros,
  signal?: AbortSignal,
): Promise<T[]> {
  const vistos = new Set<number>()
  const resultado: T[] = []
  const paginas = new Set<string>()
  let ruta: string | null = endpoint
  let inicial = true

  while (ruta) {
    if (signal?.aborted) throw new DOMException('Solicitud cancelada.', 'AbortError')
    const clave = new URL(ruta, window.location.origin).href
    if (paginas.has(clave)) throw new Error('El catálogo devolvió un ciclo de paginación.')
    paginas.add(clave)

    const response: AxiosResponse<T[] | PaginatedResponse<T>> = await axiosInstance.get<T[] | PaginatedResponse<T>>(ruta, {
      params: inicial ? parametrosValidos(params) : undefined,
      signal,
    })
    inicial = false
    const data: T[] | PaginatedResponse<T> = response.data
    const filas = Array.isArray(data) ? data : data.results
    for (const fila of filas) {
      if (!vistos.has(fila.id)) {
        vistos.add(fila.id)
        resultado.push(fila)
      }
    }
    ruta = Array.isArray(data) || !data.next ? null : rutaSiguienteSegura(data.next)
  }
  return resultado
}

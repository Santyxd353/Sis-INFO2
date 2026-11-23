/// <reference types="node" />
// @vitest-environment node
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

// Shared React setup clears Web Storage; this worker suite deliberately runs in Node.
beforeAll(() => {
  vi.stubGlobal('localStorage', { clear() {} })
  vi.stubGlobal('sessionStorage', { clear() {} })
})
afterAll(() => vi.unstubAllGlobals())

const origin = 'https://escuela.example'
const workerPath = new URL('../../public/sw.js', import.meta.url)

function harness() {
  const stores = new Map<string, Map<string, Response>>()
  const listeners = new Map<string, (event: object) => void>()
  const key = (request: Request | string) => new URL(typeof request === 'string' ? request : request.url, origin).href
  const caches = {
    keys: async () => [...stores.keys()],
    delete: async (name: string) => stores.delete(name),
    open: async (name: string) => {
      if (!stores.has(name)) stores.set(name, new Map())
      const store = stores.get(name)!
      return {
        match: async (request: Request | string) => store.get(key(request))?.clone(),
        put: async (request: Request | string, response: Response) => { store.set(key(request), response.clone()) },
      }
    },
  }
  const fetcher = vi.fn<(request: Request | string, init?: RequestInit) => Promise<Response>>(async (request) => {
    const path = new URL(key(request)).pathname
    const type = path.endsWith('.js') ? 'text/javascript' : path.endsWith('.css') ? 'text/css' : path.endsWith('.png') ? 'image/png' : path.endsWith('.webmanifest') ? 'application/manifest+json' : path.endsWith('.svg') ? 'image/svg+xml' : 'text/html'
    return new Response(path === '/offline.html' ? '<h1>Sin conexión</h1>' : `network:${path}`, { headers: { 'Content-Type': type } })
  })
  const self = {
    location: new URL(`${origin}/sw.js`),
    addEventListener: (name: string, handler: (event: object) => void) => { listeners.set(name, handler) },
    clients: { claim: vi.fn(async () => undefined) },
    skipWaiting: vi.fn(async () => undefined),
  }
  runInNewContext(readFileSync(workerPath, 'utf8'), { self, caches, fetch: fetcher, URL, Request, Response, Promise, Set, console })
  const dispatch = async (name: string, fields = {}) => {
    const pending: Promise<unknown>[] = []
    listeners.get(name)?.({ ...fields, waitUntil: (promise: Promise<unknown>) => pending.push(promise) })
    await Promise.all(pending)
  }
  const request = async (path: string, init: RequestInit & { mode?: RequestMode } = {}) => {
    const { mode, ...rest } = init
    const req = new Request(new URL(path, origin), rest)
    if (mode) Object.defineProperty(req, 'mode', { value: mode })
    let response: Promise<Response> | undefined
    const pending: Promise<unknown>[] = []
    listeners.get('fetch')?.({ request: req, respondWith: (value: Promise<Response>) => { response = value }, waitUntil: (value: Promise<unknown>) => { pending.push(value) } })
    // Requests deliberately not intercepted take the browser's normal network path.
    const result = await (response ?? fetcher(req))
    await Promise.all(pending)
    return result
  }
  return { stores, caches, fetcher, self, dispatch, request }
}

describe('worker real: privacidad y shell público', () => {
  it('instala un shell genérico y sirve recursos estáticos propios sin conexión', async () => {
    const h = harness()
    await h.dispatch('install')
    await h.request('/assets/index-Abc12345.js')
    h.fetcher.mockRejectedValue(new TypeError('offline'))
    expect(await (await h.request('/assets/index-Abc12345.js')).text()).toBe('network:/assets/index-Abc12345.js')
    expect(await (await h.request('/dashboard/portal-familiar', { mode: 'navigate' })).text()).toContain('Sin conexión')
    expect([...h.stores.values()].flatMap((store) => [...store.keys()])).not.toContain(`${origin}/dashboard/portal-familiar`)
  })

  it.each([
    ['/api/portal/familia/', {}], ['/api/portal/familia/?estudiante=7', {}],
    ['/api/token/', { method: 'POST', body: 'private' }], ['/auth/session', {}],
    ['/boletines/7.pdf', {}], ['/assets/private.pdf', {}], ['/assets/data.json', {}],
    ['/assets/index-Abc12345.js?token=secreto', {}], ['/dashboard?estudiante=7', { mode: 'navigate' }],
    ['/assets/index-Abc12345.js', { headers: { Authorization: 'Bearer secreto' } }],
    ['/assets/index-Abc12345.js', { headers: { Range: 'bytes=0-10' } }],
    ['https://externo.example/assets/index-Abc12345.js', {}],
  ] as [string, RequestInit & { mode?: RequestMode }][])('jamás almacena ni devuelve fallback para %s %j', async (path, init) => {
    const h = harness()
    await h.dispatch('install')
    const before = [...h.stores.values()].flatMap((store) => [...store.keys()])
    await h.request(path, init)
    expect([...h.stores.values()].flatMap((store) => [...store.keys()])).toEqual(before)
    h.fetcher.mockRejectedValue(new TypeError('offline'))
    await expect(h.request(path, init)).rejects.toThrow('offline')
  })

  it.each(['private', 'no-store'])('respeta Cache-Control %s incluso en un recurso estático', async (directive) => {
    const h = harness()
    await h.dispatch('install')
    h.fetcher.mockResolvedValue(new Response('private', { headers: { 'Content-Type': 'text/javascript', 'Cache-Control': directive } }))
    await h.request('/assets/index-Abc12345.js')
    h.fetcher.mockRejectedValue(new TypeError('offline'))
    await expect(h.request('/assets/index-Abc12345.js')).rejects.toThrow('offline')
  })

  it('rechaza HTML servido en lugar de JavaScript para no cachear una página privada', async () => {
    const h = harness()
    await h.dispatch('install')
    h.fetcher.mockResolvedValue(new Response('cuenta privada', { headers: { 'Content-Type': 'text/html' } }))
    await h.request('/assets/index-Abc12345.js')
    h.fetcher.mockRejectedValue(new TypeError('offline'))
    await expect(h.request('/assets/index-Abc12345.js')).rejects.toThrow('offline')
  })

  it('nunca almacena la respuesta personalizada de una navegación', async () => {
    const h = harness()
    await h.dispatch('install')
    h.fetcher.mockResolvedValue(new Response('Nombre del alumno y notas', { headers: { 'Content-Type': 'text/html' } }))
    await h.request('/dashboard/portal-familiar', { mode: 'navigate' })
    h.fetcher.mockRejectedValue(new TypeError('offline'))
    expect(await (await h.request('/dashboard/portal-familiar', { mode: 'navigate' })).text()).not.toContain('Nombre del alumno')
  })

  it('omite cookies al descargar estáticos y desactiva también la caché HTTP para APIs', async () => {
    const h = harness()
    await h.dispatch('install')
    await h.request('/assets/index-Abc12345.js')
    const staticRequest = h.fetcher.mock.calls.at(-1)![0] as Request
    expect(staticRequest.credentials).toBe('omit')
    expect(staticRequest.cache).toBe('no-store')
    await h.request('/api/portal/familia/')
    expect(h.fetcher.mock.calls.at(-1)![1]).toEqual({ cache: 'no-store' })
  })

  it('una petición autenticada no reutiliza ni siquiera un estático ya cacheado', async () => {
    const h = harness()
    await h.dispatch('install')
    await h.request('/assets/index-Abc12345.js')
    h.fetcher.mockRejectedValue(new TypeError('offline'))
    await expect(h.request('/assets/index-Abc12345.js', { headers: { Authorization: 'Bearer secreto' } })).rejects.toThrow('offline')
  })

  it('un PDF no recibe HTML offline aunque se solicite como navegación', async () => {
    const h = harness()
    await h.dispatch('install')
    h.fetcher.mockRejectedValue(new TypeError('offline'))
    await expect(h.request('/dashboard/boletines/7.pdf', { mode: 'navigate' })).rejects.toThrow('offline')
    await expect(h.request('/api/portal/familia/', { mode: 'navigate' })).rejects.toThrow('offline')
  })

  it('activa limpiando solo versiones propias y actualiza al solicitarlo', async () => {
    const h = harness()
    await h.dispatch('install')
    await h.caches.open('edugestion-hu29-static-v0')
    await h.caches.open('otra-aplicacion-v1')
    await h.dispatch('activate')
    expect(h.stores.has('edugestion-hu29-static-v0')).toBe(false)
    expect(h.stores.has('otra-aplicacion-v1')).toBe(true)
    expect(h.self.clients.claim).toHaveBeenCalledOnce()
    expect(h.self.skipWaiting).not.toHaveBeenCalled()
    await h.dispatch('message', { data: { type: 'SKIP_WAITING' }, source: { url: `${origin}/dashboard` } })
    expect(h.self.skipWaiting).toHaveBeenCalledOnce()
  })
})

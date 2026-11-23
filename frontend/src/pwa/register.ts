type PwaCallbacks = {
  onUpdate: (worker: ServiceWorker) => void
  onControlling: () => void
  onError: () => void
}

export function canRegisterPwa(location: Pick<Location, 'hostname' | 'protocol'> = window.location, secure = window.isSecureContext): boolean {
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)
  const enabled = import.meta.env.PROD || (local && import.meta.env.VITE_PWA_DEV === 'true')
  return Boolean(enabled && secure && (location.protocol === 'https:' || local))
}

export function registerPwa({ onUpdate, onControlling, onError }: PwaCallbacks): () => void {
  if (!canRegisterPwa() || !('serviceWorker' in navigator)) return () => {}
  let disposed = false
  let registration: ServiceWorkerRegistration | undefined
  let installing: ServiceWorker | null = null
  const checkWaiting = () => {
    if (!disposed && registration?.waiting) onUpdate(registration.waiting)
  }
  const stateChange = () => { if (installing?.state === 'installed') checkWaiting() }
  const updateFound = () => {
    installing?.removeEventListener('statechange', stateChange)
    installing = registration?.installing ?? null
    installing?.addEventListener('statechange', stateChange)
  }
  const update = () => { void registration?.update().catch(() => { /* Retry on the next connection. */ }) }
  navigator.serviceWorker.addEventListener('controllerchange', onControlling)
  window.addEventListener('online', update)
  void navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' }).then((result) => {
    if (disposed) return
    registration = result
    checkWaiting()
    registration.addEventListener('updatefound', updateFound)
    updateFound()
  }).catch(() => { if (!disposed) onError() })

  return () => {
    disposed = true
    navigator.serviceWorker.removeEventListener('controllerchange', onControlling)
    window.removeEventListener('online', update)
    registration?.removeEventListener('updatefound', updateFound)
    installing?.removeEventListener('statechange', stateChange)
  }
}

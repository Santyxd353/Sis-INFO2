import { useEffect, useRef, useState } from 'react'
import { Download, RefreshCw, WifiOff } from 'lucide-react'
import { registerPwa } from './register'
import './pwa.css'

interface InstallPrompt extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

function standalone() {
  return window.matchMedia?.('(display-mode: standalone)').matches ||
    Boolean((navigator as Navigator & { standalone?: boolean }).standalone)
}

export default function PwaStatus() {
  const [online, setOnline] = useState(navigator.onLine)
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const [installed, setInstalled] = useState(standalone)
  const [instructions, setInstructions] = useState(false)
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null)
  const [registrationError, setRegistrationError] = useState(false)
  const [installError, setInstallError] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [updating, setUpdating] = useState(false)
  const applyingUpdate = useRef(false)
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

  useEffect(() => {
    const offline = () => setOnline(false)
    const online = () => setOnline(true)
    const beforeInstall = (event: Event) => { event.preventDefault(); setPrompt(event as InstallPrompt) }
    const appInstalled = () => { setInstalled(true); setPrompt(null); setInstructions(false) }
    window.addEventListener('offline', offline)
    window.addEventListener('online', online)
    window.addEventListener('beforeinstallprompt', beforeInstall)
    window.addEventListener('appinstalled', appInstalled)
    const unregisterListeners = registerPwa({
      onUpdate: setWaiting,
      onControlling: () => { if (applyingUpdate.current) window.location.reload() },
      onError: () => setRegistrationError(true),
    })
    return () => {
      window.removeEventListener('offline', offline)
      window.removeEventListener('online', online)
      window.removeEventListener('beforeinstallprompt', beforeInstall)
      window.removeEventListener('appinstalled', appInstalled)
      unregisterListeners()
    }
  }, [])

  const install = async () => {
    if (!prompt || installing) return
    setInstalling(true)
    setInstallError(false)
    try {
      await prompt.prompt()
      const choice = await prompt.userChoice
      if (choice.outcome === 'accepted') setInstalled(true)
    } catch { setInstallError(true) }
    finally { setPrompt(null); setInstalling(false) }
  }

  const showInstall = !installed && !dismissed && (prompt || ios)
  if (online && !showInstall && !waiting && !registrationError && !installError) return null

  return <aside className="pwa-status" aria-label="Estado de la aplicación">
    {!online && <p className="pwa-notice" role="status"><WifiOff size={18} aria-hidden="true" /><span><strong>Sin conexión.</strong> Los datos del portal y los documentos requieren conexión. Vuelve a intentar cuando tengas red.</span></p>}
    {registrationError && <p className="pwa-notice" role="status">No se pudo preparar el modo sin conexión. Puedes seguir usando la aplicación con internet.</p>}
    {installError && <p className="pwa-notice" role="status">No se pudo abrir la instalación. Intenta desde el menú de tu navegador.</p>}
    {waiting && <div className="pwa-card">
      <p><strong>Hay una actualización disponible.</strong> Guarda tu trabajo antes de recargar.</p>
      <button className="pwa-primary" disabled={updating} onClick={() => {
        applyingUpdate.current = true
        setUpdating(true)
        waiting.postMessage({ type: 'SKIP_WAITING' })
      }}><RefreshCw size={16} aria-hidden="true" />{updating ? 'Actualizando…' : 'Actualizar aplicación'}</button>
    </div>}
    {showInstall && <div className="pwa-card">
      <p><strong>EduGestión en tu dispositivo</strong><br />Accede desde tu pantalla de inicio. Consultar información requiere internet.</p>
      <div className="pwa-actions">
        {prompt ? <button className="pwa-primary" disabled={installing} onClick={() => { void install() }}><Download size={16} aria-hidden="true" />{installing ? 'Instalando…' : 'Instalar aplicación'}</button>
          : <button className="pwa-primary" onClick={() => setInstructions(true)}>Cómo instalar la aplicación</button>}
        <button className="pwa-secondary" onClick={() => { setDismissed(true); setPrompt(null); setInstructions(false) }}>Ahora no</button>
      </div>
      {instructions && <div className="pwa-instructions">
        <p>Abre este sitio en Safari, toca <strong>Compartir</strong> y elige <strong>Añadir a pantalla de inicio</strong>.</p>
        <button className="pwa-secondary" onClick={() => setInstructions(false)}>Cerrar instrucciones</button>
      </div>}
    </div>}
  </aside>
}

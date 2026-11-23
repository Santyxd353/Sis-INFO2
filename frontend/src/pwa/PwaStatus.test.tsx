import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PwaStatus from './PwaStatus'

beforeEach(() => {
  vi.stubEnv('PROD', false)
  vi.stubEnv('VITE_PWA_DEV', 'false')
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
})
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals() })

function installEvent(outcome: 'accepted' | 'dismissed' = 'accepted') {
  const event = new Event('beforeinstallprompt', { cancelable: true })
  return Object.assign(event, { prompt: vi.fn(async () => undefined), userChoice: Promise.resolve({ outcome, platform: 'web' }) })
}

describe('PWA: acciones y estado accesibles', () => {
  it('invoca la instalación solo tras pulsar Instalar y elimina el aviso al aceptar', async () => {
    render(<PwaStatus />)
    const event = installEvent()
    act(() => { window.dispatchEvent(event) })
    expect(event.defaultPrevented).toBe(true)
    expect(event.prompt).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Instalar aplicación' }))
    await waitFor(() => expect(event.prompt).toHaveBeenCalledOnce())
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Instalar aplicación' })).not.toBeInTheDocument())
  })

  it('permite descartar la propuesta sin invocar el diálogo del navegador', () => {
    render(<PwaStatus />)
    const event = installEvent()
    act(() => { window.dispatchEvent(event) })
    fireEvent.click(screen.getByRole('button', { name: 'Ahora no' }))
    expect(event.prompt).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Instalar aplicación' })).not.toBeInTheDocument()
  })

  it('retira un evento de instalación ya usado cuando el navegador lo rechaza', async () => {
    render(<PwaStatus />)
    const event = installEvent('dismissed')
    act(() => { window.dispatchEvent(event) })
    fireEvent.click(screen.getByRole('button', { name: 'Instalar aplicación' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Instalar aplicación' })).not.toBeInTheDocument())
  })

  it('explica cómo instalar en iOS sin fingir un diálogo disponible', () => {
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit Safari/604.1')
    render(<PwaStatus />)
    fireEvent.click(screen.getByRole('button', { name: 'Cómo instalar la aplicación' }))
    expect(screen.getByText(/Compartir/).closest('p')).toHaveTextContent('Añadir a pantalla de inicio')
    expect(screen.queryByRole('button', { name: 'Instalar aplicación' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar instrucciones' }))
    expect(screen.queryByText(/Compartir/)).not.toBeInTheDocument()
  })

  it('anuncia la falta de red y se retira al recuperar conexión', () => {
    render(<PwaStatus />)
    act(() => { window.dispatchEvent(new Event('offline')) })
    expect(screen.getByRole('status')).toHaveTextContent(/Sin conexión/)
    expect(screen.getByRole('status')).toHaveTextContent(/requieren conexión/)
    act(() => { window.dispatchEvent(new Event('online')) })
    expect(screen.queryByText(/Sin conexión/)).not.toBeInTheDocument()
  })

  it('ofrece actualizar cuando hay un worker en espera y activa solo por petición del usuario', async () => {
    vi.stubEnv('PROD', true)
    vi.stubGlobal('isSecureContext', true)
    const waiting = { postMessage: vi.fn() }
    const registration = Object.assign(new EventTarget(), { waiting, installing: null, update: vi.fn(async () => undefined) })
    const serviceWorker = Object.assign(new EventTarget(), { register: vi.fn(async () => registration), controller: {} })
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: serviceWorker })
    const view = render(<PwaStatus />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Actualizar aplicación' })).toBeInTheDocument())
    expect(waiting.postMessage).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar aplicación' }))
    expect(waiting.postMessage).toHaveBeenCalledWith({ type: 'SKIP_WAITING' })
    expect(serviceWorker.register).toHaveBeenCalledWith('/sw.js', { scope: '/', updateViaCache: 'none' })
    view.unmount()
    delete (navigator as unknown as Record<string, unknown>).serviceWorker
  })
})

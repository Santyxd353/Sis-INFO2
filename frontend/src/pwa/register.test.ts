import { describe, expect, it, vi } from 'vitest'
import { canRegisterPwa } from './register'

describe('registro PWA solo en entornos autorizados', () => {
  it.each([
    [false, 'false', 'https://escuela.example', true, false],
    [false, 'true', 'https://escuela.example', true, false],
    [false, 'true', 'http://localhost:5173', true, true],
    [false, 'true', 'http://127.0.0.1:5173', true, true],
    [true, 'false', 'https://escuela.example', true, true],
    [true, 'false', 'http://escuela.example', false, false],
  ])('producción=%s prueba=%s url=%s seguro=%s → %s', (prod, dev, url, secure, expected) => {
    vi.stubEnv('PROD', prod)
    vi.stubEnv('VITE_PWA_DEV', dev)
    expect(canRegisterPwa(new URL(url), secure)).toBe(expected)
    vi.unstubAllEnvs()
  })
})

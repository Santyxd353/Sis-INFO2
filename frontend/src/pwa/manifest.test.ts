/// <reference types="node" />
// @vitest-environment node
import { readFileSync } from 'node:fs'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

beforeAll(() => {
  vi.stubGlobal('localStorage', { clear() {} })
  vi.stubGlobal('sessionStorage', { clear() {} })
})
afterAll(() => vi.unstubAllGlobals())

describe('artefactos de instalación PWA', () => {
  it('inicia el portal dentro de su scope y proporciona iconos PNG válidos', () => {
    const manifest = JSON.parse(readFileSync(new URL('../../public/manifest.webmanifest', import.meta.url), 'utf8'))
    expect(manifest.lang).toBe('es')
    expect(manifest.display).toBe('standalone')
    expect(manifest.scope).toBe('/')
    expect(manifest.start_url).toBe('/dashboard')
    expect(manifest.icons).toEqual(expect.arrayContaining([
      expect.objectContaining({ sizes: '192x192', type: 'image/png', purpose: 'any' }),
      expect.objectContaining({ sizes: '512x512', type: 'image/png', purpose: 'any' }),
      expect.objectContaining({ sizes: '512x512', type: 'image/png', purpose: 'maskable' }),
    ]))
    for (const icon of manifest.icons) {
      const png = readFileSync(new URL(`../../public${icon.src}`, import.meta.url))
      expect(png.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
      expect(`${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`).toBe(icon.sizes)
    }
  })
})

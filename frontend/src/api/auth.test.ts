import { describe, expect, it } from 'vitest'
import {
  AUTH_ACCESS_TOKEN_KEY,
  AUTH_REFRESH_TOKEN_KEY,
  AUTH_USER_KEY,
  clearSession,
  getStoredUser,
  removeLegacySession,
  saveSession,
  updateTokens,
} from './auth'
import { testUser } from '../test/fixtures'

describe('almacenamiento de sesión JWT', () => {
  it('guarda access, refresh y usuario por separado en sessionStorage', () => {
    saveSession({ access: 'access-1', refresh: 'refresh-1', user: testUser })
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access-1')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('refresh-1')
    expect(getStoredUser()).toEqual(testUser)
    expect(localStorage).toHaveLength(0)
  })

  it('reemplaza access y conserva refresh cuando no hay rotación', () => {
    saveSession({ access: 'old', refresh: 'same', user: testUser })
    updateTokens('new')
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('new')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('same')
  })

  it('reemplaza también el refresh rotado', () => {
    saveSession({ access: 'old', refresh: 'old-refresh', user: testUser })
    updateTokens('new', 'new-refresh')
    expect(sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)).toBe('new-refresh')
  })

  it('limpia toda la sesión y las claves heredadas', () => {
    saveSession({ access: 'access', refresh: 'refresh', user: testUser })
    localStorage.setItem('token', 'legacy')
    sessionStorage.setItem('datosDelUsuario', '{}')
    clearSession(false)
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBeNull()
    expect(sessionStorage).toHaveLength(0)
    expect(localStorage).toHaveLength(0)
  })

  it('elimina credenciales heredadas sin borrar las nuevas', () => {
    saveSession({ access: 'access', refresh: 'refresh', user: testUser })
    localStorage.setItem('auth_token', 'legacy')
    removeLegacySession()
    expect(sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)).toBe('access')
    expect(localStorage.getItem('auth_token')).toBeNull()
  })
})

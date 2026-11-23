import type { Usuario } from '../app/modelos/Usuarios'

export const AUTH_ACCESS_TOKEN_KEY = 'auth_access_token'
export const AUTH_REFRESH_TOKEN_KEY = 'auth_refresh_token'
export const AUTH_USER_KEY = 'auth_user'
export const AUTH_SESSION_CLEARED_EVENT = 'auth:session-cleared'

const legacyKeys = ['token', 'auth_token', 'datosDelUsuario']

export interface AuthSession { access: string; refresh: string; user: Usuario }

export const getAccessToken = () => sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY)
export const getRefreshToken = () => sessionStorage.getItem(AUTH_REFRESH_TOKEN_KEY)

export const getStoredUser = (): Usuario | null => {
  const value = sessionStorage.getItem(AUTH_USER_KEY)
  if (!value) return null
  try { return JSON.parse(value) as Usuario } catch {
    sessionStorage.removeItem(AUTH_USER_KEY)
    return null
  }
}

export const saveSession = ({ access, refresh, user }: AuthSession) => {
  sessionStorage.setItem(AUTH_ACCESS_TOKEN_KEY, access)
  sessionStorage.setItem(AUTH_REFRESH_TOKEN_KEY, refresh)
  sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
}

export const updateTokens = (access: string, refresh?: string) => {
  sessionStorage.setItem(AUTH_ACCESS_TOKEN_KEY, access)
  if (refresh) sessionStorage.setItem(AUTH_REFRESH_TOKEN_KEY, refresh)
}

export const storeUser = (user: Usuario) => sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))

export const removeLegacySession = () => {
  legacyKeys.forEach((key) => {
    localStorage.removeItem(key)
    sessionStorage.removeItem(key)
  })
}

export const clearSession = (notify = true) => {
  sessionStorage.removeItem(AUTH_ACCESS_TOKEN_KEY)
  sessionStorage.removeItem(AUTH_REFRESH_TOKEN_KEY)
  sessionStorage.removeItem(AUTH_USER_KEY)
  removeLegacySession()
  if (notify) window.dispatchEvent(new Event(AUTH_SESSION_CLEARED_EVENT))
}

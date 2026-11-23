import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import AxiosInstance, { authAxios } from '../../api/axiosInstance'
import {
  AUTH_SESSION_CLEARED_EVENT,
  clearSession,
  getAccessToken,
  getRefreshToken,
  removeLegacySession,
  saveSession,
  storeUser,
} from '../../api/auth'
import { canEffectivePermission, type Usuario } from '../modelos/Usuarios'

interface AuthContextType {
  user: Usuario | null
  loading: boolean
  setUser: React.Dispatch<React.SetStateAction<Usuario | null>>
  login: (identifier: string, password: string) => Promise<Usuario>
  logout: () => Promise<void>
  hasRole: (allowedRoles: string[]) => boolean
  isSuperAdmin: () => boolean
  isAdmin: () => boolean
  isProfesor: () => boolean
  isEstudiante: () => boolean
  isTutor: () => boolean
  permisosCargando: boolean
  can: (modelo: string, accion: string) => boolean
  puedeComponente: (componente: string) => boolean
  puedeEditarComponente: (componente: string) => boolean
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  setUser: () => {},
  login: async () => { throw new Error('AuthProvider no está disponible.') },
  logout: async () => {},
  hasRole: () => false,
  isSuperAdmin: () => false,
  isAdmin: () => false,
  isProfesor: () => false,
  isEstudiante: () => false,
  isTutor: () => false,
  permisosCargando: false,
  can: () => false,
  puedeComponente: () => true,
  puedeEditarComponente: () => false,
})

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<Usuario | null>(null)
  const [loading, setLoading] = useState(() => Boolean(getAccessToken() || getRefreshToken()))

  useEffect(() => {
    removeLegacySession()
    if (!getAccessToken() && !getRefreshToken()) return

    let activo = true
    AxiosInstance.get<Usuario>('/usuarios/perfil/')
      .then((res) => {
        if (!activo) return
        setUser(res.data)
        storeUser(res.data)
      })
      .catch(() => {
        if (!activo) return
        setUser(null)
        clearSession(false)
      })
      .finally(() => {
        if (activo) setLoading(false)
      })

    return () => {
      activo = false
    }
  }, [])

  useEffect(() => {
    const sessionCleared = () => {
      setUser(null)
      setLoading(false)
    }
    window.addEventListener(AUTH_SESSION_CLEARED_EVENT, sessionCleared)
    return () => window.removeEventListener(AUTH_SESSION_CLEARED_EVENT, sessionCleared)
  }, [])

  const login = async (identifier: string, password: string) => {
    const normalizedIdentifier = identifier.trim()
    const credentials = normalizedIdentifier.includes('@')
      ? { email: normalizedIdentifier, password }
      : { username: normalizedIdentifier, password }
    const response = await authAxios.post<{ access: string; refresh: string; user: Usuario }>(
      '/usuarios/login/',
      credentials,
    )
    const { access, refresh, user: authenticatedUser } = response.data
    if (!access || !refresh || !authenticatedUser) {
      throw new Error('La respuesta de autenticación está incompleta.')
    }
    saveSession({ access, refresh, user: authenticatedUser })
    setUser(authenticatedUser)
    return authenticatedUser
  }

  const logout = async () => {
    const refresh = getRefreshToken()
    try {
      if (refresh) await AxiosInstance.post('/usuarios/logout/', { refresh })
    } catch (error) {
      console.error('Error al cerrar sesión:', error)
    } finally {
      clearSession(false)
      setUser(null)
    }
  }

  const hasRole = useCallback((allowedRoles: string[]): boolean => {
    if (!user) return false
    const rolesNormalizados = allowedRoles.map((rol) => rol.toLowerCase())
    return rolesNormalizados.includes(user.rol.nombre.toLowerCase())
  }, [user])

  const isSuperAdmin = useCallback(() => hasRole(['superadmin']) && user?.alcance?.tipo === 'GLOBAL', [hasRole, user])
  const isAdmin = useCallback(() => hasRole(['admin']), [hasRole])
  const isProfesor = useCallback(() => hasRole(['profesor']), [hasRole])
  const isEstudiante = useCallback(() => hasRole(['estudiante']), [hasRole])
  const isTutor = useCallback(() => hasRole(['tutor']), [hasRole])

  const permisosCargando = loading

  const can = useCallback((modelo: string, accion: string) => {
    if (isSuperAdmin() && user?.alcance?.tipo === 'GLOBAL') return true
    return canEffectivePermission(user, modelo, accion)
  }, [isSuperAdmin, user])

  // HU-SE02 regla 4: los permisos de interfaz vienen fusionados desde el backend.
  const puedeComponente = useCallback((componente: string) => {
    if (isSuperAdmin() && user?.alcance?.tipo === 'GLOBAL') return true
    const fila = user?.permisos_ui?.find((item) => item.componente === componente)
    // Sin configuración el componente es visible (opt-out).
    return fila ? fila.visible : true
  }, [isSuperAdmin, user])

  const puedeEditarComponente = useCallback((componente: string) => {
    if (isSuperAdmin() && user?.alcance?.tipo === 'GLOBAL') return true
    const fila = user?.permisos_ui?.find((item) => item.componente === componente)
    // Denegación por defecto: sin configuración no se puede editar.
    return fila ? fila.editable : false
  }, [isSuperAdmin, user])

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        setUser,
        login,
        logout,
        hasRole,
        isSuperAdmin,
        isAdmin,
        isProfesor,
        isEstudiante,
        isTutor,
        permisosCargando,
        can,
        puedeComponente,
        puedeEditarComponente,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// El hook comparte archivo con el proveedor para mantener una API de autenticación única.
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext)

import type { ReactElement } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { resolveVisualProfile } from '../navigation/navigationConfig'
import type { VisualProfile } from '../navigation/types'

export default function RequireProfile({profiles,children}:{profiles:VisualProfile[];children:ReactElement}) {
  const {user,loading}=useAuth()
  if(loading)return <div className="grid min-h-screen place-items-center">Restaurando sesión...</div>
  return profiles.includes(resolveVisualProfile(user))?children:<Navigate to="/dashboard/no-permission" replace/>
}

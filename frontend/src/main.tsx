import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { AuthProvider } from './app/contexts/AuthContext'
import AppearanceSettings from './app/appearance/AppearanceSettings'
import PwaStatus from './pwa/PwaStatus'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <AppearanceSettings />
        <PwaStatus />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)

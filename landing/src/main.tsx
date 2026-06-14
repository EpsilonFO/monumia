import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { LandingPage, SIGNUP_PATH } from './LandingPage'
import { SignupPage } from './SignupPage'

// Routeur minimal : le fallback SPA de nginx sert index.html pour toute route,
// on choisit ici la page à afficher selon le chemin. Pas de dépendance ajoutée.
const strip = (p: string) => p.replace(/\/+$/, '')
const isSignup = strip(window.location.pathname) === strip(SIGNUP_PATH)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isSignup ? <SignupPage /> : <LandingPage />}
  </StrictMode>,
)

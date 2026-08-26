import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { LandingPage, SIGNUP_PATH } from './LandingPage'
import { SignupPage } from './SignupPage'
import { CguPage, PrivacyPage, CGU_PATH, PRIVACY_PATH } from './LegalPages'

// Routeur minimal : le fallback SPA de nginx sert index.html pour toute route,
// on choisit ici la page à afficher selon le chemin. Pas de dépendance ajoutée.
const strip = (p: string) => p.replace(/\/+$/, '')
const path = strip(window.location.pathname)

function pageForPath() {
  if (path === strip(SIGNUP_PATH)) return <SignupPage />
  if (path === strip(CGU_PATH)) return <CguPage />
  if (path === strip(PRIVACY_PATH)) return <PrivacyPage />
  return <LandingPage />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {pageForPath()}
  </StrictMode>,
)

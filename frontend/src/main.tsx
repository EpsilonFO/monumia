import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { rechargerSurMorceauPerdu } from './lib/morceau-perdu'
import { demarrerMesureAudience } from './lib/posthog'
import { useAuthStore } from './stores/useAuthStore'

rechargerSurMorceauPerdu()
// Ne démarre rien sans VITE_POSTHOG_KEY. Les administrateurs ne sont pas comptés.
demarrerMesureAudience(() => Boolean(useAuthStore.getState().user?.estAdmin))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

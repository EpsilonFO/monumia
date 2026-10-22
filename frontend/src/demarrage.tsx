import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { demarrerMesureAudience } from './lib/posthog'
import { useAuthStore } from './stores/useAuthStore'

// Importé par main.tsx APRÈS l'initialisation d'i18n : aucun module de
// l'application ne s'évalue avant que la langue et ses traductions soient prêtes.
export function demarrer() {
  // Ne démarre rien sans VITE_POSTHOG_KEY. Les administrateurs ne sont pas comptés.
  demarrerMesureAudience(() => Boolean(useAuthStore.getState().user?.estAdmin))

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

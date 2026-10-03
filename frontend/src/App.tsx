import { useEffect, useState } from 'react';
import { RouterProvider } from 'react-router';
import { router } from './router';
import { Toaster } from '@/components/ui/sonner';
import { useAuthStore } from '@/stores/useAuthStore';
import { ensureFreshAccessToken } from '@/lib/token-refresh';
import { YbugWidget } from '@/components/shared/YbugWidget';

/**
 * Le token d'accès vit en mémoire : au chargement, si un profil persiste
 * (session antérieure), on tente un refresh silencieux via le cookie httpOnly
 * avant de rendre le router — sinon ProtectedRoute flasherait /login.
 */
function App() {
  const [restoring, setRestoring] = useState(
    () => Boolean(useAuthStore.getState().user) && !useAuthStore.getState().token,
  );

  useEffect(() => {
    if (!restoring) return;
    ensureFreshAccessToken().finally(() => setRestoring(false));
  }, [restoring]);

  if (restoring) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ background: 'var(--app-bg)' }}
      />
    );
  }

  return (
    <>
      <RouterProvider router={router} />
      <Toaster position="bottom-right" />
      {/* Bouton de retour bêta : ne rend rien sans VITE_YBUG_ID. */}
      <YbugWidget />
    </>
  );
}

export default App;

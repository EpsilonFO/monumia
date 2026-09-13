import { Navigate } from 'react-router';
import { useAuthStore } from '@/stores/useAuthStore';
import { ROUTES } from '@/constants/routes';

interface AdminRouteProps {
  children: React.ReactNode;
}

/**
 * Garde de la page d'administration du catalogue.
 *
 * `estAdmin` vient du profil (`GET /auth/me`), donc du serveur — mais il ne
 * garde rien : c'est un confort d'affichage, qui évite de proposer une page
 * dont chaque appel répondrait 403. L'autorité est `require_admin`, côté API.
 *
 * Redirection silencieuse vers l'espace, sans paywall ni message : une page
 * d'exploitation n'est pas une offre à vendre, et son existence n'a pas à être
 * annoncée à qui n'y a pas accès.
 */
export function AdminRoute({ children }: AdminRouteProps) {
  const user = useAuthStore((s) => s.user);

  if (!user?.estAdmin) {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }

  return <>{children}</>;
}

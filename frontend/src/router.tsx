import { createBrowserRouter, Navigate, useSearchParams } from 'react-router';
import { useAuthStore } from '@/stores/useAuthStore';
import { AppLayout } from '@/components/layout/AppLayout';
import { LoginPage } from '@/pages/login/LoginPage';
import { ResetPasswordPage } from '@/pages/login/ResetPasswordPage';
import { AuthCallbackPage } from '@/pages/login/AuthCallbackPage';
import { TarifsPage } from '@/pages/tarifs/TarifsPage';
import { BlogLayout } from '@/components/blog/BlogLayout';
import { BlogIndexPage } from '@/pages/blog/BlogIndexPage';
import { BlogCategoryPage } from '@/pages/blog/BlogCategoryPage';
import { BlogArticlePage } from '@/pages/blog/BlogArticlePage';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
// Owner / Commune pages
import { DashboardPage } from '@/pages/dashboard/DashboardPage';
import { MonumentsListPage } from '@/pages/monuments/MonumentsListPage';
import { MonumentWizardPage } from '@/pages/monuments/MonumentWizardPage';
import { MonumentDetailPage } from '@/pages/monuments/MonumentDetailPage';
import { ProjetWizardPage } from '@/pages/projets/ProjetWizardPage';
import { ProjetDetailPage } from '@/pages/projets/ProjetDetailPage';
import { AideProjectPage } from '@/pages/projets/AideProjectPage';
import { DossierDetailPage } from '@/pages/projets/DossierDetailPage';
import { DocumentsPage } from '@/pages/documents/DocumentsPage';
import { ProfilePage } from '@/pages/profile/ProfilePage';
import { InvitationLandingPage } from '@/pages/invitation/InvitationLandingPage';
import { ROUTES } from '@/constants/routes';
import { useOffre, useOffreChargee } from '@/hooks/useOffre';

/**
 * Ancien wizard unifié : `/app/projets/nouveau`, avec `?monument=<id>` pour
 * « Refaire le questionnaire ». Sans monument c'est une création de fiche, donc
 * le wizard monument ; avec, on renvoie sur la page du monument, d'où
 * l'utilisateur choisit le projet à refaire (l'ancien lien ne dit pas lequel).
 */
// eslint-disable-next-line react-refresh/only-export-components
function LegacyWizardRedirect() {
  const [searchParams] = useSearchParams();
  const monumentId = searchParams.get('monument');
  return (
    <Navigate
      to={monumentId ? `${ROUTES.MONUMENT_DETAIL(monumentId)}?tab=projets` : ROUTES.MONUMENT_NEW}
      replace
    />
  );
}

/**
 * Le tableau de bord est réservé à l'offre Multi-monuments : sur un seul
 * monument, il n'agrège rien que la fiche ne montre déjà.
 *
 * Ce garde renvoie sur « Mes monuments », et NON sur les tarifs, alors que
 * l'onglet de la barre haute mène bien aux tarifs (cf. navItemsPour). Les deux
 * ne répondent pas à la même intention : `/app` est la racine de l'espace, là
 * où `RootRedirect` dépose tout le monde à la connexion. Y répondre par la page
 * de vente ferait atterrir chaque ouverture de session sur un argumentaire.
 * Cliquer l'onglet, en revanche, est une demande explicite.
 *
 * On ATTEND la réponse du serveur avant de rediriger. L'état initial est
 * l'offre gratuite (par prudence, cf. useOffre), et trancher dessus éjecterait
 * un abonné vers « Mes monuments » à chaque rechargement — le temps que
 * /billing/access revienne.
 */
// eslint-disable-next-line react-refresh/only-export-components
function DashboardRoute() {
  const offre = useOffre();
  const charge = useOffreChargee();
  if (!charge) return <div className="min-h-[40vh]" />;
  if (!offre.dashboard) return <Navigate to={ROUTES.MONUMENTS} replace />;
  return <DashboardPage />;
}

// Root: send logged-in users to their dashboard, others to login.
// The landing page (separate origin) links here so the app picks the right space.
// eslint-disable-next-line react-refresh/only-export-components
function RootRedirect() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  if (!user || !token) return <Navigate to="/login" replace />;
  if (user.accountType === 'collaborateur') return <Navigate to={ROUTES.MONUMENTS} replace />;
  return <Navigate to="/app" replace />;
}

export const router = createBrowserRouter([
  // Root redirects by auth state (landing page is now on monumia.fr)
  {
    path: '/',
    element: <RootRedirect />,
  },

  // Login page (public)
  {
    path: '/login',
    element: <LoginPage />,
  },

  // Reset password landing page (public — arrives from email link)
  {
    path: '/reset-password',
    element: <ResetPasswordPage />,
  },

  // OAuth callback landing page (public — arrives from Supabase redirect)
  {
    path: '/auth/callback',
    element: <AuthCallbackPage />,
  },

  // Tarifs page (public)
  {
    path: '/tarifs',
    element: <TarifsPage />,
  },

  // Blog (public)
  {
    path: '/blog',
    element: <BlogLayout />,
    children: [
      { index: true, element: <BlogIndexPage /> },
      { path: 'categorie/:categorySlug', element: <BlogCategoryPage /> },
      { path: 'article/:slug', element: <BlogArticlePage /> },
    ],
  },

  // Invitation acceptance page (public — no auth required)
  {
    path: '/invitation/:token',
    element: <InvitationLandingPage />,
  },

  // Les deux wizards — plein écran immersif, hors du shell AppLayout.
  {
    path: '/app/monuments/nouveau',
    element: (
      <ProtectedRoute>
        <MonumentWizardPage />
      </ProtectedRoute>
    ),
  },
  {
    // `?projet=<id>` : « Refaire le questionnaire » d'un projet existant.
    path: '/app/monuments/:monumentId/projets/nouveau',
    element: (
      <ProtectedRoute>
        <ProjetWizardPage />
      </ProtectedRoute>
    ),
  },
  // Legacy : l'ancien wizard unifié vivait ici, hors AppLayout lui aussi.
  {
    path: '/app/projets/nouveau',
    element: (
      <ProtectedRoute>
        <LegacyWizardRedirect />
      </ProtectedRoute>
    ),
  },

  // Owner / Commune app (protégé)
  {
    path: '/app',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      // `/app` reste la racine de l'espace : le garde renvoie sur « Mes
      // monuments » quand l'offre n'ouvre pas le tableau de bord.
      { index: true, element: <DashboardRoute /> },
      // Monuments : la liste et la fiche du bien
      { path: 'monuments', element: <MonumentsListPage /> },
      { path: 'monuments/:monumentId', element: <MonumentDetailPage /> },
      // Projets de travaux
      // `:projetId` peut être un id de MONUMENT sur les vieux liens (emails,
      // notifications) : ProjetDetailPage le résout à l'exécution et redirige.
      { path: 'projets/:projetId', element: <ProjetDetailPage /> },
      { path: 'projets/:projetId/aides/:aideId', element: <AideProjectPage /> },
      { path: 'projets/:projetId/dossiers/:dossierId', element: <DossierDetailPage /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'profil', element: <ProfilePage /> },
      // Redirections legacy → liste des monuments
      { path: 'projets', element: <Navigate to={ROUTES.MONUMENTS} replace /> },
      { path: 'dossiers', element: <Navigate to={ROUTES.MONUMENTS} replace /> },
      { path: 'dossiers/:dossierId', element: <Navigate to={ROUTES.MONUMENTS} replace /> },
      { path: 'aides', element: <Navigate to={ROUTES.MONUMENTS} replace /> },
      { path: 'aides/:aideId', element: <Navigate to={ROUTES.MONUMENTS} replace /> },
    ],
  },

  // Catch-all → login
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

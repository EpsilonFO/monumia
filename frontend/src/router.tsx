import { createBrowserRouter, Navigate, useParams } from 'react-router';
import { useAuthStore } from '@/stores/useAuthStore';
import { AppLayout } from '@/components/layout/AppLayout';
import { BtpLayout } from '@/components/layout/BtpLayout';
import { OnboardingPage } from '@/pages/onboarding/OnboardingPage';
import { SegmentChoice } from '@/pages/onboarding/SegmentChoice';
import { OnboardingProfile } from '@/pages/onboarding/OnboardingProfile';
import { OnboardingMonument } from '@/pages/onboarding/OnboardingMonument';
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
import { ProjectsListPage } from '@/pages/projets/ProjectsListPage';
import { ProjectWizardPage } from '@/pages/projets/ProjectWizardPage';
import { ProjectDetailPage } from '@/pages/projets/ProjectDetailPage';
import { AideProjectPage } from '@/pages/projets/AideProjectPage';
import { DossierDetailPage } from '@/pages/projets/DossierDetailPage';
import { DocumentsPage } from '@/pages/documents/DocumentsPage';
import { TemplateLibraryPage } from '@/pages/templates/TemplateLibraryPage';
import { ProfilePage } from '@/pages/profile/ProfilePage';
// BTP pages
import { BtpDashboardPage } from '@/pages/btp/BtpDashboardPage';
import { BtpProspectsPage } from '@/pages/btp/BtpProspectsPage';
import { BtpProspectDetailPage } from '@/pages/btp/BtpProspectDetailPage';
import { BtpAidesPage } from '@/pages/btp/BtpAidesPage';
import { BtpDocumentsPage } from '@/pages/btp/BtpDocumentsPage';
import { BtpProfilePage } from '@/pages/btp/BtpProfilePage';
import { InvitationLandingPage } from '@/pages/invitation/InvitationLandingPage';

// Legacy redirect: /app/monuments/:monumentId → /app/projets/:monumentId (id preserved)
// eslint-disable-next-line react-refresh/only-export-components
function LegacyMonumentRedirect() {
  const { monumentId } = useParams();
  return <Navigate to={`/app/projets/${monumentId ?? ''}`} replace />;
}

// Root: send logged-in users to their dashboard (segment-aware), others to login.
// The landing page (separate origin) links here so the app picks the right space.
// eslint-disable-next-line react-refresh/only-export-components
function RootRedirect() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  if (!user || !token) return <Navigate to="/login" replace />;
  if (user.segment === 'btp') return <Navigate to="/btp" replace />;
  if (user.accountType === 'collaborateur') return <Navigate to="/app/projets" replace />;
  return <Navigate to="/app" replace />;
}

export const router = createBrowserRouter([
  // Root redirects by auth/segment (landing page is now on monumia.fr)
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

  // Onboarding — credentials kept in memory only (usePendingRegistrationStore)
  {
    path: '/onboarding',
    element: <OnboardingPage />,
    children: [
      { index: true, element: <SegmentChoice /> },
      { path: 'profil', element: <OnboardingProfile /> },
      { path: 'monument', element: <OnboardingMonument /> },
    ],
  },

  // Wizard de création — plein écran immersif, hors du shell AppLayout.
  // Le chemin est inchangé : « Refaire le questionnaire » (?monument=id) et
  // tous les ROUTES.PROJET_NEW continuent de fonctionner.
  {
    path: '/app/projets/nouveau',
    element: (
      <ProtectedRoute>
        <ProjectWizardPage />
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
      { index: true, element: <DashboardPage /> },
      // Unified Projet tab
      { path: 'projets', element: <ProjectsListPage /> },
      { path: 'projets/:projetId', element: <ProjectDetailPage /> },
      { path: 'projets/:projetId/aides/:aideId', element: <AideProjectPage /> },
      { path: 'projets/:projetId/dossiers/:dossierId', element: <DossierDetailPage /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'modeles', element: <TemplateLibraryPage /> },
      { path: 'profil', element: <ProfilePage /> },
      // Legacy redirects → unified Projet tab
      { path: 'monuments', element: <Navigate to="/app/projets" replace /> },
      { path: 'monuments/:monumentId', element: <LegacyMonumentRedirect /> },
      { path: 'dossiers', element: <Navigate to="/app/projets" replace /> },
      { path: 'dossiers/:dossierId', element: <Navigate to="/app/projets" replace /> },
      { path: 'aides', element: <Navigate to="/app/projets" replace /> },
      { path: 'aides/:aideId', element: <Navigate to="/app/projets" replace /> },
    ],
  },

  // BTP app (protégé)
  {
    path: '/btp',
    element: (
      <ProtectedRoute>
        <BtpLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <BtpDashboardPage /> },
      { path: 'prospects', element: <BtpProspectsPage /> },
      { path: 'prospects/:prospectId', element: <BtpProspectDetailPage /> },
      { path: 'aides', element: <BtpAidesPage /> },
      { path: 'documents', element: <BtpDocumentsPage /> },
      { path: 'profil', element: <BtpProfilePage /> },
    ],
  },

  // Catch-all → login
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

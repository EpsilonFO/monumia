import { createBrowserRouter, Navigate } from 'react-router';
import { AppLayout } from '@/components/layout/AppLayout';
import { BtpLayout } from '@/components/layout/BtpLayout';
import { OnboardingPage } from '@/pages/onboarding/OnboardingPage';
import { SegmentChoice } from '@/pages/onboarding/SegmentChoice';
import { OnboardingProfile } from '@/pages/onboarding/OnboardingProfile';
import { OnboardingMonument } from '@/pages/onboarding/OnboardingMonument';
import { LoginPage } from '@/pages/login/LoginPage';
import LandingPage from '@/pages/LandingPage';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
// Owner / Commune pages
import { DashboardPage } from '@/pages/dashboard/DashboardPage';
import { MonumentsListPage } from '@/pages/monuments/MonumentsListPage';
import { MonumentDetailPage } from '@/pages/monuments/MonumentDetailPage';
import { AideDetailPage } from '@/pages/aides/AideDetailPage';
import { DossiersListPage } from '@/pages/dossiers/DossiersListPage';
import { DossierDetailPage } from '@/pages/dossiers/DossierDetailPage';
import { DocumentsPage } from '@/pages/documents/DocumentsPage';
import { ProfilePage } from '@/pages/profile/ProfilePage';
// BTP pages
import { BtpDashboardPage } from '@/pages/btp/BtpDashboardPage';
import { BtpProspectsPage } from '@/pages/btp/BtpProspectsPage';
import { BtpProspectDetailPage } from '@/pages/btp/BtpProspectDetailPage';
import { BtpAidesPage } from '@/pages/btp/BtpAidesPage';
import { BtpDocumentsPage } from '@/pages/btp/BtpDocumentsPage';
import { BtpProfilePage } from '@/pages/btp/BtpProfilePage';

export const router = createBrowserRouter([
  // Landing Page (public)
  {
    path: '/',
    element: <LandingPage />,
  },

  // Login page (public)
  {
    path: '/login',
    element: <LoginPage />,
  },

  // Onboarding — accessible uniquement avec pending-register en session
  {
    path: '/onboarding',
    element: <OnboardingPage />,
    children: [
      { index: true, element: <SegmentChoice /> },
      { path: 'profil', element: <OnboardingProfile /> },
      { path: 'monument', element: <OnboardingMonument /> },
    ],
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
      { path: 'monuments', element: <MonumentsListPage /> },
      { path: 'monuments/:monumentId', element: <MonumentDetailPage /> },
      { path: 'aides', element: <Navigate to="/app/dossiers" replace /> },
      { path: 'aides/:aideId', element: <AideDetailPage /> },
      { path: 'dossiers', element: <DossiersListPage /> },
      { path: 'dossiers/:dossierId', element: <DossierDetailPage /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'profil', element: <ProfilePage /> },
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

  // Catch-all → landing page
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

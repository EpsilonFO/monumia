import { createBrowserRouter, Navigate } from 'react-router';
import { AppLayout } from '@/components/layout/AppLayout';
import { OnboardingPage } from '@/pages/onboarding/OnboardingPage';
import { SegmentChoice } from '@/pages/onboarding/SegmentChoice';
import { OnboardingProfile } from '@/pages/onboarding/OnboardingProfile';
import { OnboardingMonument } from '@/pages/onboarding/OnboardingMonument';
import { DashboardPage } from '@/pages/dashboard/DashboardPage';
import { MonumentsListPage } from '@/pages/monuments/MonumentsListPage';
import { MonumentDetailPage } from '@/pages/monuments/MonumentDetailPage';
import { AidesListPage } from '@/pages/aides/AidesListPage';
import { AideDetailPage } from '@/pages/aides/AideDetailPage';
import { DossiersListPage } from '@/pages/dossiers/DossiersListPage';
import { DossierDetailPage } from '@/pages/dossiers/DossierDetailPage';
import { DocumentsPage } from '@/pages/documents/DocumentsPage';
import { ProfilePage } from '@/pages/profile/ProfilePage';

export const router = createBrowserRouter([
  {
    path: '/onboarding',
    element: <OnboardingPage />,
    children: [
      { index: true, element: <SegmentChoice /> },
      { path: 'profil', element: <OnboardingProfile /> },
      { path: 'monument', element: <OnboardingMonument /> },
    ],
  },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'monuments', element: <MonumentsListPage /> },
      { path: 'monuments/:monumentId', element: <MonumentDetailPage /> },
      { path: 'aides', element: <AidesListPage /> },
      { path: 'aides/:aideId', element: <AideDetailPage /> },
      { path: 'dossiers', element: <DossiersListPage /> },
      { path: 'dossiers/:dossierId', element: <DossierDetailPage /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'profil', element: <ProfilePage /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

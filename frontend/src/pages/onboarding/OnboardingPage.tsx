import { Outlet } from 'react-router';
import { AuthLayout } from '@/components/layout/AuthLayout';

/**
 * Cadre des étapes d'inscription. Réutilise la coquille d'authentification
 * (panneau bleu + atelier crème) pour une continuité visuelle totale entre
 * connexion, inscription et arrivée dans l'application.
 */
export function OnboardingPage() {
  return (
    <AuthLayout
      panelEyebrow="Création de compte"
      panelHeadline={
        <>
          Bienvenue sur<br />
          <span style={{ color: '#f17105' }}>Monumia</span>
        </>
      }
      panelDescription="Quelques étapes pour configurer votre espace et identifier les aides adaptées à votre patrimoine."
      contentClassName="max-w-2xl"
    >
      <Outlet />
    </AuthLayout>
  );
}

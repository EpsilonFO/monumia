import { useEffect, useState } from 'react';
import { Navigate } from 'react-router';
import { useAuthStore } from '@/stores/useAuthStore';
import { useBillingStore } from '@/stores/useBillingStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { monumentService } from '@/services/monument.service';
import { destinationCompte } from '@/lib/destination-compte';
import { OFFRE_GRATUITE } from '@/lib/offres';
import { ROUTES } from '@/constants/routes';

/**
 * `/mon-compte` : l'aiguillage où arrive « Mon compte » depuis la landing.
 *
 * La page ne montre rien — elle charge les deux seules choses qui décident de
 * la destination (les droits du compte et ses monuments), puis redirige. Elle
 * vit hors de `AppLayout` exprès : afficher le shell de l'application pour le
 * quitter aussitôt ferait clignoter une barre de navigation.
 *
 * Le chargement est fait ici plutôt que laissé à `AppLayout` parce qu'il faut
 * savoir que la liste des monuments est ARRIVÉE : un compte qui a un bien et
 * un compte dont la requête n'a pas encore répondu ont le même store vide, et
 * le second serait envoyé enregistrer un monument qu'il possède déjà. Les
 * réponses sont posées dans les stores au passage : `AppLayout` les rechargera
 * de toute façon, mais la page d'arrivée s'affiche alors déjà remplie.
 */
export function MonComptePage() {
  const accountType = useAuthStore((s) => s.user?.accountType);
  const setMonuments = useMonumentStore((s) => s.setMonuments);
  const loadAccess = useBillingStore((s) => s.loadAccess);
  const [destination, setDestination] = useState<string | null>(null);

  useEffect(() => {
    let vivant = true;
    (async () => {
      try {
        // `loadAccess` ne rejette jamais (il absorbe son erreur et laisse les
        // hooks retomber sur l'offre gratuite) : seule la liste des monuments
        // peut échouer ici.
        const [, monuments] = await Promise.all([loadAccess(), monumentService.getAll()]);
        if (!vivant) return;
        setMonuments(monuments);
        setDestination(
          destinationCompte({
            offre: useBillingStore.getState().access?.offre ?? OFFRE_GRATUITE,
            monumentIds: monuments.map((m) => m.id),
            accountType,
          }),
        );
      } catch (err) {
        // Repli sur la liste : elle est ouverte à toutes les offres, et elle
        // montre aussi bien les monuments du compte que l'invitation à en
        // enregistrer un. Rien d'irréversible n'y est proposé par erreur.
        console.error('Destination du compte indéterminable', err);
        if (vivant) setDestination(ROUTES.MONUMENTS);
      }
    })();
    return () => {
      vivant = false;
    };
  }, [accountType, loadAccess, setMonuments]);

  if (!destination) {
    // Même écran d'attente qu'au démarrage de l'application (cf. App.tsx) :
    // vide plutôt qu'un contenu qui disparaîtrait aussitôt.
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ background: 'var(--app-bg)' }}
      />
    );
  }

  return <Navigate to={destination} replace />;
}

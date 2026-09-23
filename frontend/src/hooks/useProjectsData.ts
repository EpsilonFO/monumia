import { useEffect, useState } from 'react';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { dashboardService } from '@/services/dashboard.service';

/**
 * Charge tout ce dont les cartes projet ont besoin (monuments, dossiers,
 * digests d'aides, suivis) et dit quand l'ensemble est prêt à s'afficher.
 *
 * Un seul appel : `GET /dashboard`. Auparavant il en fallait 4 + 2N pour N
 * projets, en deux vagues (les diagnostics et les suivis attendaient la liste
 * des monuments), et chacun repayait la vérification du token côté serveur.
 * L'attente « tout ou rien » d'origine n'a plus lieu d'être — il n'y a plus
 * qu'une réponse, donc plus de cartes qui « sautent » à l'arrivée des
 * diagnostics.
 *
 * Rafraîchir au montage reste voulu : revenir sur l'onglet reflète les
 * changements (projets, dossiers) faits par les autres membres, sans recharger
 * la page. Au démarrage, la requête est déjà partie de `AppLayout` : celle-ci la
 * rejoint au lieu d'en envoyer une seconde.
 *
 * Le squelette ne s'affiche que s'il n'y a RIEN à montrer : des monuments déjà
 * en store — relus du cache local ou chargés par une page précédente —
 * s'affichent pendant le rafraîchissement.
 */
export function useProjectsData(): { loading: boolean } {
  const token = useAuthStore((s) => s.token);
  // Lu à chaque rendu, et non figé au premier : au démarrage à froid, les
  // monuments arrivent souvent AVANT que cet appel-ci ne soit réglé.
  const aDesDonnees = useMonumentStore((s) => s.monuments.length > 0);

  // « Réglé » = l'appel est terminé, succès OU échec. Sans ce suivi, un appel en
  // échec laisserait le squelette affiché pour toujours.
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    if (!token) return;
    let actif = true;
    dashboardService
      .load()
      .catch(console.error)
      .finally(() => {
        if (actif) setSettled(true);
      });
    return () => {
      actif = false;
    };
  }, [token]);

  return { loading: !settled && !aDesDonnees };
}

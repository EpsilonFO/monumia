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
 * la page. Les stores déjà garnis restent affichés pendant ce rafraîchissement.
 */
export function useProjectsData(): { loading: boolean } {
  const token = useAuthStore((s) => s.token);
  const monuments = useMonumentStore((s) => s.monuments);

  // « Réglé » = l'appel est terminé, succès OU échec. Sans ce suivi, un appel en
  // échec laisserait le squelette affiché pour toujours.
  const [settled, setSettled] = useState(monuments.length > 0);

  useEffect(() => {
    if (!token) return;
    dashboardService
      .load()
      .catch(console.error)
      .finally(() => setSettled(true));
  }, [token]);

  return { loading: !settled };
}

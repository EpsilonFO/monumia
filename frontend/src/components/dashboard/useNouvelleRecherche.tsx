import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { PaywallDialog } from '@/components/shared/Paywall';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { OFFRE_GRATUITE, sousLePlafond } from '@/lib/offres';
import { projectPermissions } from '@/lib/project-permissions';
import { ROUTES } from '@/constants/routes';
import type { Monument } from '@/types';

export interface NouvelleRecherche {
  /** Les monuments où l'on peut lancer un projet : ceux dont on est co-propriétaire ou plus. */
  candidats: Monument[];
  /** Ouvre le wizard d'un nouveau projet sur ce monument, ou le paywall si son offre est au plafond. */
  lancer: (monumentId: string) => void;
  /** Le paywall, à poser une fois dans la page. */
  dialogue: ReactNode;
}

/**
 * « Nouvelle recherche d'aides » : un nouveau projet sur un monument. Mêmes
 * gardes que « Nouveau projet » sur la page du monument : le rôle (co-propriétaire
 * ou plus, `projectPermissions`), puis le plafond de projets de l'offre qui
 * gouverne CE monument (`monument.offre`), le paywall se posant devant quand il
 * est atteint. Tant que le monument vient du cache local, son offre n'est pas
 * connue : le clic ne tranche pas.
 */
export function useNouvelleRecherche(): NouvelleRecherche {
  const navigate = useNavigate();
  const userId = useAuthStore((s) => s.user?.id);
  const monuments = useMonumentStore((s) => s.monuments);
  const projets = useProjetStore((s) => s.projets);
  const [paywall, setPaywall] = useState<Monument | null>(null);

  const candidats = useMemo(
    () => monuments.filter((m) => {
      // Relu du cache, un monument n'a pas encore son rôle : le propriétaire se reconnaît à son id.
      const role = m.myRole ?? (m.userId === userId ? 'owner' : null);
      return projectPermissions(role).canEditProject;
    }),
    [monuments, userId],
  );

  const lancer = useCallback((monumentId: string) => {
    const m = monuments.find((x) => x.id === monumentId);
    if (!m || m.depuisLeCache) return;
    const offre = m.offre ?? OFFRE_GRATUITE;
    const deja = projets.filter((p) => p.monumentId === m.id).length;
    if (!sousLePlafond(offre.projetsMax, deja)) {
      setPaywall(m);
      return;
    }
    navigate(ROUTES.PROJET_NEW(m.id));
  }, [monuments, projets, navigate]);

  const projetsMax = paywall?.offre?.projetsMax ?? OFFRE_GRATUITE.projetsMax;
  const dialogue = (
    <PaywallDialog
      open={!!paywall}
      onOpenChange={(o) => { if (!o) setPaywall(null); }}
      offre="Veille"
      titre="Menez autant de chantiers qu'il en faut"
      description={
        projetsMax === null
          ? 'L’offre Veille rend vos projets de travaux illimités, et vous prévient avant chaque date limite.'
          : `Votre offre couvre ${projetsMax} projets par monument. L’offre Veille les rend illimités, et vous prévient avant chaque date limite.`
      }
      monumentId={paywall?.id}
    />
  );

  return { candidats, lancer, dialogue };
}

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MonumentInput, ProjectQuestionnaireAnswers, WorkType } from '@/types';

/**
 * Le brouillon du parcours DÉCOUVERTE : ce qu'un visiteur a décrit avant
 * d'avoir un compte.
 *
 * Rien ne part en base avant l'inscription — ni monument, ni projet, ni
 * diagnostic. Il n'y a pas de compte anonyme possible : `monuments.user_id` et
 * `project_members.user_id` ont une clé étrangère vers `public.users` (email,
 * prénom, nom NOT NULL, aucun trigger de création), et `prevent_owner_change`
 * rend `user_id` immuable même en service role. D'où la stratégie brouillon
 * local puis REJEU : le front rappelle `POST /monuments` puis
 * `POST /monuments/{id}/projets` une fois le compte créé (cf.
 * `lib/brouillon-invite.ts`).
 *
 * `localStorage` et non `sessionStorage` : le parcours s'interrompt (un devis à
 * retrouver, une protection à vérifier) et doit se reprendre le lendemain, dans
 * un onglet neuf.
 */

/** Où en est le visiteur. Sert à rouvrir le wizard là où il l'a laissé. */
export type EtapeBrouillon = 'intention' | 'travaux' | 'questionnaire' | 'inscription';

interface BrouillonInviteState {
  /** La fiche du bien, telle que `POST /monuments` l'attend. */
  monument: MonumentInput | null;
  /** Intentions de l'étape « Votre projet » (clé réservée `_raisons` au rejeu). */
  raisons: string[];
  /** `null` : pas de réponse ; `[]` : « Pas encore déterminé ». Même tri-state
   *  que le wizard et que la colonne `projets.travaux_envisages`. */
  travaux: WorkType[] | null;
  /** Réponses au questionnaire, SANS les clés réservées : `_raisons` est
   *  recomposé au rejeu depuis `raisons`, une seule source pour cette valeur. */
  answers: ProjectQuestionnaireAnswers;
  etape: EtapeBrouillon;
  /** Posés PENDANT le rejeu, pour son idempotence : « Réessayer » après un
   *  échec sur le projet ne doit pas créer un second monument. */
  monumentId: string | null;
  projetId: string | null;
  /** Date de création du brouillon (ISO), pour la purge à 7 jours. */
  creeLe: string | null;

  setMonument: (monument: MonumentInput) => void;
  setCadrage: (raisons: string[], travaux: WorkType[] | null) => void;
  setAnswers: (answers: ProjectQuestionnaireAnswers) => void;
  setEtape: (etape: EtapeBrouillon) => void;
  marquerMonumentCree: (monumentId: string) => void;
  marquerProjetCree: (projetId: string) => void;
  vider: () => void;
}

const ETAT_INITIAL = {
  monument: null,
  raisons: [],
  travaux: null,
  answers: {},
  etape: 'intention' as EtapeBrouillon,
  monumentId: null,
  projetId: null,
  creeLe: null,
};

/** Au-delà, le brouillon est jeté à la réhydratation : le catalogue d'aides et
 *  l'ontologie bougent, et reprendre un questionnaire d'il y a un mois
 *  poserait des questions qui n'existent plus. */
export const TTL_JOURS = 7;

/** Version du FORMAT persisté. À incrémenter dès qu'un champ change de forme —
 *  une version inconnue est jetée, jamais migrée (cf. `migrate`). */
export const VERSION_BROUILLON = 1;

export function estPerime(creeLe: string | null): boolean {
  if (!creeLe) return false;
  const t = Date.parse(creeLe);
  if (Number.isNaN(t)) return true;
  return Date.now() - t > TTL_JOURS * 24 * 60 * 60 * 1000;
}

export const useBrouillonInviteStore = create<BrouillonInviteState>()(
  persist(
    (set) => ({
      ...ETAT_INITIAL,

      // Changer de monument périme le cadrage : les travaux et les réponses
      // portaient sur un autre bien, et les questions du QCM dépendent de sa
      // protection comme de sa commune.
      setMonument: (monument) =>
        set((state) => {
          const memeBien =
            state.monument !== null &&
            state.monument.nom === monument.nom &&
            state.monument.codeInsee === monument.codeInsee &&
            state.monument.commune === monument.commune;
          return {
            monument,
            etape: 'intention',
            creeLe: state.creeLe ?? new Date().toISOString(),
            ...(memeBien ? {} : { raisons: [], travaux: null, answers: {} }),
          };
        }),

      setCadrage: (raisons, travaux) => set({ raisons, travaux }),

      setAnswers: (answers) => set({ answers }),

      setEtape: (etape) => set({ etape }),

      marquerMonumentCree: (monumentId) => set({ monumentId }),

      marquerProjetCree: (projetId) => set({ projetId }),

      vider: () => set({ ...ETAT_INITIAL }),
    }),
    {
      name: 'monumia-brouillon-invite',
      version: VERSION_BROUILLON,
      // Une version inconnue est JETÉE, jamais migrée : un brouillon est une
      // saisie de quelques minutes, pas une donnée de compte. Deviner la forme
      // d'un état écrit par une autre version coûterait plus cher que de
      // reposer trois questions.
      migrate: (persisted, version) =>
        version === VERSION_BROUILLON ? (persisted as BrouillonInviteState) : { ...ETAT_INITIAL },
      // Purge à la réhydratation : le TTL se vérifie à l'ouverture de la page,
      // pas au moment d'écrire.
      onRehydrateStorage: () => (state) => {
        if (state && estPerime(state.creeLe)) state.vider();
      },
    }
  )
);

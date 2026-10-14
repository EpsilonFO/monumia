/**
 * Mesure d'audience anonyme : démarrage de PostHog et envoi des événements
 * métier. La politique (quelle clé, quoi retirer de chaque envoi) est dans
 * `lib/mesure-audience.ts` ; ce module ne fait que l'appliquer.
 *
 * Sans `VITE_POSTHOG_KEY`, rien ne se passe : la bibliothèque n'est pas
 * téléchargée et `suivre` ne fait rien. Les services l'appellent donc sans
 * condition, y compris dans les tests.
 */

import type { PostHog } from 'posthog-js';
import {
  clePostHog,
  mesureRefusee,
  nettoyerEvenement,
  type EvenementMesure,
} from '@/lib/mesure-audience';

/** Instance de l'UE : les données restent en Europe. */
const HOTE_POSTHOG = 'https://eu.i.posthog.com';

let instance: Promise<PostHog> | null = null;

/**
 * Démarre la mesure, une fois pour toutes, au chargement de l'application.
 *
 * `compteInterne` et l'opposition sont relus à chaque envoi plutôt que figés au
 * démarrage : un administrateur qui se connecte en cours de route, ou un
 * utilisateur qui s'oppose depuis son profil, cesse d'être compté sur-le-champ.
 */
export function demarrerMesureAudience(compteInterne: () => boolean): void {
  const cle = clePostHog();
  if (!cle || instance) return;

  // Import différé : la bibliothèque n'alourdit pas le premier chargement, et
  // un build sans clé ne la télécharge jamais.
  instance = import('posthog-js').then(({ default: posthog }) => {
    posthog.init(cle, {
      api_host: HOTE_POSTHOG,
      defaults: '2026-08-30',

      // Rien sur le poste : ni cookie ni stockage local. PostHog compte les
      // visiteurs uniques par une empreinte calculée et renouvelée chaque
      // jour sur ses serveurs. Exige le réglage « Cookieless server hash
      // mode » du projet, sans lequel PostHog JETTE ces événements.
      cookieless_mode: 'always',
      // Jamais de fiche par personne, même si un `identify` traînait un jour.
      person_profiles: 'never',

      // Pages vues à chaque navigation de la SPA, et clics. Le texte et les
      // attributs des éléments cliqués restent dans le navigateur : un clic
      // sur une carte de monument enverrait sinon son nom.
      capture_pageview: 'history_change',
      autocapture: true,
      mask_all_text: true,
      mask_all_element_attributes: true,
      capture_heatmaps: true,

      // Tout le reste est fermé dans le code, pas seulement dans les réglages
      // du projet : une case cochée par erreur dans PostHog ne doit pas
      // suffire à filmer les écrans des utilisateurs.
      disable_session_recording: true,
      disable_external_dependency_loading: true,
      disable_surveys: true,
      disable_product_tours: true,
      disable_conversations: true,
      advanced_disable_flags: true,
      capture_exceptions: false,
      capture_performance: false,
      capture_dead_clicks: false,

      // « Do Not Track » vaut opposition, sans rien avoir à cocher.
      respect_dnt: true,

      before_send: (evenement) =>
        nettoyerEvenement(evenement, compteInterne() || mesureRefusee()),
    });
    return posthog;
  });
}

/** Envoie un événement métier. Sans clé, ne fait rien. */
export function suivre(evenement: EvenementMesure): void {
  if (!instance) return;
  const proprietes = 'proprietes' in evenement ? evenement.proprietes : undefined;
  void instance.then((posthog) => posthog.capture(evenement.nom, proprietes));
}

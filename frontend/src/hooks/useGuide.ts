import { useEffect } from 'react';
import { driver, type Driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import '@/components/shared/guide.css';
import { ETAPES_MIN, VISITES, etapesJouables, selecteurAncre, type GuideId } from '@/lib/guides';
import { guideVuLocalement } from '@/lib/guides-local';
import { useAuthStore } from '@/stores/useAuthStore';

/** Laisse l'écran se poser (animations d'entrée, données) avant de surligner. */
const DELAI_DEMARRAGE_MS = 600;

/** Affiché, et pas derrière un paywall (`inert`) ni masqué aux lecteurs d'écran. */
function estAffiche(el: HTMLElement): boolean {
  if (el.closest('[inert]') || el.closest('[aria-hidden="true"]')) return false;
  if (el.getClientRects().length === 0) return false;
  return window.getComputedStyle(el).visibility !== 'hidden';
}

/**
 * Le premier élément AFFICHÉ qui porte l'ancre. Une même ancre peut exister
 * deux fois (le lien « Mes documents » de la barre du haut, caché sur mobile,
 * et celui de la barre du bas) : on vise celle qu'on voit.
 */
function elementDeLAncre(ancre: string): HTMLElement | null {
  const candidats = document.querySelectorAll<HTMLElement>(selecteurAncre(ancre));
  return [...candidats].find(estAffiche) ?? null;
}

/**
 * Joue la visite guidée d'un écran à la première arrivée : une fois les
 * données de la page chargées (`pret`), si elle n'a pas été vue, et s'il reste
 * au moins deux étapes dont l'élément est visible. « Compris » comme « Passer »
 * la marquent vue, sur le compte et sur l'appareil.
 */
export function useGuide(id: GuideId, { pret }: { pret: boolean }): void {
  const dejaVu = useAuthStore((s) => !!s.user?.guidesVus?.[id]);
  const marquerGuideVu = useAuthStore((s) => s.marquerGuideVu);

  useEffect(() => {
    if (!pret || dejaVu || guideVuLocalement(id)) return;
    let visite: Driver | null = null;
    const minuteur = window.setTimeout(() => {
      const etapes = etapesJouables(VISITES[id], (a) => elementDeLAncre(a) !== null);
      if (etapes.length < ETAPES_MIN) return;
      let marquee = false;
      const marquer = () => {
        if (marquee) return;
        marquee = true;
        marquerGuideVu(id);
      };
      visite = driver({
        popoverClass: 'guide-bulle',
        overlayOpacity: 0.45,
        stagePadding: 6,
        stageRadius: 12,
        showProgress: etapes.length > 1,
        progressText: '{{current}} sur {{total}}',
        nextBtnText: 'Suivant',
        prevBtnText: 'Précédent',
        doneBtnText: 'Compris',
        showButtons: ['next', 'previous'],
        // « Passer » toujours visible, à gauche des boutons de navigation.
        onPopoverRender: (popover, { driver: d }) => {
          const passer = document.createElement('button');
          passer.type = 'button';
          passer.className = 'guide-passer';
          passer.textContent = 'Passer';
          passer.addEventListener('click', () => d.destroy());
          popover.footer.prepend(passer);
        },
        // Fermée par « Compris », « Passer », Échap ou un clic à côté : vue.
        onDestroyed: marquer,
        steps: etapes.map((e) => ({
          element: () => elementDeLAncre(e.ancre) ?? document.body,
          popover: { title: e.titre, description: e.texte, side: e.cote ?? 'bottom', align: 'start' },
        })),
      });
      visite.drive();
    }, DELAI_DEMARRAGE_MS);
    return () => {
      window.clearTimeout(minuteur);
      // Quitter l'écran en pleine visite la ferme (et la marque vue).
      visite?.destroy();
    };
  }, [id, pret, dejaVu, marquerGuideVu]);
}

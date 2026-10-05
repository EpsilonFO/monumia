import { useCallback, useEffect, useRef } from 'react';

/** Apparition douce d'un bloc quand il entre à l'écran (classe `reveal`). */
export function useApparition<T extends HTMLElement>() {
  return useCallback((el: T | null) => {
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        el.classList.add('in');
        io.disconnect();
      },
      { threshold: 0.08 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
}

/** Fait défiler jusqu'à un point du règlement et le signale un instant. Passe
 *  après le rendu qui l'a déplié : deux images, le temps que React valide. */
export function signalerPoint(id: string) {
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      const el = document.getElementById(`p-${id}`);
      if (!el) return;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('flash');
      setTimeout(() => el.classList.remove('flash'), 1600);
    }),
  );
}

export const EVENEMENT_OUVRIR = 'fiche:ouvrir';

/** Déplie une section repliée de la fiche (`Repli`) depuis ailleurs : la barre
 *  collante (« Réunir les pièces »), le lien d'un conseil vers une démarche. */
export function ouvrirSection(id: string) {
  window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, { detail: id }));
}

/** Hauteur de la barre de l'application, plus la marge sous laquelle la colonne se cale. */
const HAUT_COLLANT = 75.5;
/** Marge laissée sous la colonne quand elle se cale en bas de l'écran. */
const MARGE_BAS = 16;

/**
 * Colonne « L'essentiel » : elle défile d'abord avec la page, puis reste à côté
 * du contenu jusqu'en bas. Rien ne défile DANS la colonne.
 *
 * C'est un `position: sticky` dont le `top` dépend de sa hauteur : quand elle
 * tient dans l'écran, elle se colle sous la barre (`HAUT_COLLANT`) ; quand elle
 * est plus haute, son `top` devient négatif, si bien qu'elle monte avec la page
 * jusqu'à ce que son bas apparaisse, puis se cale là. Le CSS ne connaît pas la
 * hauteur d'un élément : elle est mesurée ici et posée dans `--side-top`.
 */
export function useColonneCollante<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const caler = () => {
      const top = Math.min(HAUT_COLLANT, window.innerHeight - el.offsetHeight - MARGE_BAS);
      el.style.setProperty('--side-top', `${top}px`);
    };
    caler();
    const ro = new ResizeObserver(caler);
    ro.observe(el);
    window.addEventListener('resize', caler);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', caler);
    };
  }, []);
  return ref;
}

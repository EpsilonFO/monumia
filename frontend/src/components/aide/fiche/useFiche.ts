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

/** Vitesse de lecture du défilement automatique, en pixels par seconde. */
const VITESSE = 14;
/** La remontée va plus vite : on a déjà tout lu. */
const VITESSE_RETOUR = VITESSE * 6;
/** Pause en haut et en bas, le temps de lire la première ou la dernière ligne. */
const PAUSE_BOUT = 3000;
/** Après un défilement à la main, on laisse la main dix secondes. */
const REPRISE_APRES_MAIN = 10_000;

/**
 * Défilement automatique d'un panneau trop haut pour son cadre (« L'essentiel ») :
 * sans lui, une ligne restait cachée sous le bas du panneau, et rien ne disait
 * qu'on pouvait la faire venir. Il descend lentement, marque une pause, remonte,
 * et recommence.
 *
 * La main reste à l'utilisateur : molette, doigt, clavier ou barre de défilement
 * l'arrêtent dix secondes, et il attend tant que la souris est posée dessus
 * (un texte qui bouge sous le pointeur ne se lit pas). Rien ne bouge si tout
 * tient dans le cadre, ni pour qui a demandé moins d'animations au système.
 */
export function useDefilementAuto<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    let pos = el.scrollTop;
    let sens: 1 | -1 = 1;
    let attendreJusqua = performance.now() + PAUSE_BOUT;
    let survol = false;
    let dernier = performance.now();
    let raf = 0;

    const laMain = () => {
      pos = el.scrollTop;
      attendreJusqua = performance.now() + REPRISE_APRES_MAIN;
    };
    // Un défilement qui n'est pas le nôtre (barre de défilement, ancre) : la
    // position s'écarte de celle qu'on vient de poser.
    const surDefilement = () => {
      if (Math.abs(el.scrollTop - pos) > 2) laMain();
    };
    const entree = () => {
      survol = true;
    };
    const sortie = () => {
      survol = false;
      pos = el.scrollTop;
      attendreJusqua = Math.max(attendreJusqua, performance.now() + 1500);
    };

    const tick = (t: number) => {
      const dt = Math.min(t - dernier, 100) / 1000;
      dernier = t;
      const max = el.scrollHeight - el.clientHeight;
      if (max > 4 && !survol && t >= attendreJusqua) {
        pos += sens * (sens > 0 ? VITESSE : VITESSE_RETOUR) * dt;
        if (pos >= max) {
          pos = max;
          sens = -1;
          attendreJusqua = t + PAUSE_BOUT;
        } else if (pos <= 0) {
          pos = 0;
          sens = 1;
          attendreJusqua = t + PAUSE_BOUT;
        }
        el.scrollTop = pos;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    const options = { passive: true } as const;
    el.addEventListener('scroll', surDefilement, options);
    el.addEventListener('wheel', laMain, options);
    el.addEventListener('touchstart', laMain, options);
    el.addEventListener('keydown', laMain);
    el.addEventListener('pointerenter', entree);
    el.addEventListener('pointerleave', sortie);
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('scroll', surDefilement);
      el.removeEventListener('wheel', laMain);
      el.removeEventListener('touchstart', laMain);
      el.removeEventListener('keydown', laMain);
      el.removeEventListener('pointerenter', entree);
      el.removeEventListener('pointerleave', sortie);
    };
  }, []);
  return ref;
}

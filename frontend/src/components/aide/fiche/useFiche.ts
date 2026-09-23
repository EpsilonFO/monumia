import { useCallback } from 'react';

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

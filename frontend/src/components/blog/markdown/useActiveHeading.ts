import { useEffect, useState } from 'react';

/**
 * Renvoie l'id du titre `##` actuellement « actif » (le plus haut visible sous
 * l'en-tête). Met à jour en continu au défilement — utilisé par le sommaire
 * latéral pour surligner la section en cours de lecture.
 */
export function useActiveHeading(ids: string[]): string {
  const [active, setActive] = useState<string>(ids[0] ?? '');

  useEffect(() => {
    if (ids.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive((visible[0].target as HTMLElement).id);
      },
      { rootMargin: '-100.5px 0px -70% 0px', threshold: 0 },
    );
    const els = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el != null);
    els.forEach((el) => observer.observe(el));

    // En bas de page, forcer la dernière section : son titre est passé au-dessus
    // de la zone de détection, l'observer ne le verrait jamais « actif » sinon.
    const onScroll = () => {
      const atBottom =
        window.innerHeight + window.scrollY >=
        document.documentElement.scrollHeight - 4;
      if (atBottom) setActive(ids[ids.length - 1]);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    return () => {
      observer.disconnect();
      window.removeEventListener('scroll', onScroll);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids.join('|')]);

  return active;
}

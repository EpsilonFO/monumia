import { useCallback, useEffect, useState } from 'react';
import {
  READ_KEY,
  parseReadSlugs,
  serializeReadSlugs,
  withRead,
  countRead as countReadPure,
} from './readState';

/** Lecture initiale sûre (SSR / localStorage indisponible → ensemble vide). */
function readInitial(): Set<string> {
  if (typeof window === 'undefined') return new Set();
  try {
    return parseReadSlugs(window.localStorage.getItem(READ_KEY));
  } catch {
    return new Set();
  }
}

/**
 * Suivi de lecture du blog en localStorage, sans compte. Se resynchronise entre
 * onglets via l'event `storage`. Toute erreur de stockage est silencieuse : le
 * blog reste pleinement navigable.
 */
export function useReadArticles() {
  const [readSlugs, setReadSlugs] = useState<Set<string>>(readInitial);

  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === READ_KEY) setReadSlugs(parseReadSlugs(e.newValue));
    }
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const markRead = useCallback((slug: string) => {
    setReadSlugs((prev) => {
      if (prev.has(slug)) return prev;
      const next = withRead(prev, slug);
      try {
        window.localStorage.setItem(READ_KEY, serializeReadSlugs(next));
      } catch {
        /* stockage indisponible : on garde l'état en mémoire */
      }
      return next;
    });
  }, []);

  const isRead = useCallback((slug: string) => readSlugs.has(slug), [readSlugs]);
  const countRead = useCallback((slugs: string[]) => countReadPure(readSlugs, slugs), [readSlugs]);

  return { readSlugs, isRead, markRead, countRead };
}

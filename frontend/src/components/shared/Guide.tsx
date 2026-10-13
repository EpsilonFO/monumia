import { useGuide } from '@/hooks/useGuide';
import type { GuideId } from '@/lib/guides';

/**
 * La visite guidée d'un écran, à poser dans son rendu CHARGÉ : un composant
 * plutôt qu'un appel de hook, pour ne pas dépendre des retours anticipés de la
 * page (squelettes, erreurs). Ne rend rien.
 */
export function Guide({ id, pret = true }: { id: GuideId; pret?: boolean }) {
  useGuide(id, { pret });
  return null;
}

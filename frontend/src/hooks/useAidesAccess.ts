import { useBillingStore } from '@/stores/useBillingStore';
import { resolveAidesAccess, type AidesAccess } from '@/lib/aides-access';

/**
 * Accès au détail des aides, projet par projet. La décision elle-même vit dans
 * `resolveAidesAccess` (pure, testée) : ce hook ne fait que lire le store.
 */
export function useAidesAccess(monumentId?: string): AidesAccess {
  const access = useBillingStore((s) => s.access);
  const loaded = useBillingStore((s) => s.loaded);
  return resolveAidesAccess(access, monumentId, loaded);
}

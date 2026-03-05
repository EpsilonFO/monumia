import { useAuthStore } from '@/stores/useAuthStore';
import type { UserSegment } from '@/types';

export function useSegment(): UserSegment {
  const user = useAuthStore((s) => s.user);
  return user?.segment ?? 'commune';
}

export function useIsCommune(): boolean {
  return useSegment() === 'commune';
}

export function useIsPrive(): boolean {
  return useSegment() === 'prive';
}

export function useIsBtp(): boolean {
  return useSegment() === 'btp';
}

export function useSegmentLabel() {
  const segment = useSegment();
  return {
    segment,
    isCommune: segment === 'commune',
    isPrive: segment === 'prive',
    // Segment-adapted vocabulary
    ownerLabel: segment === 'commune' ? 'Commune' : 'Propriétaire',
    ownerDocLabel:
      segment === 'commune'
        ? 'Délibération du conseil municipal'
        : 'Titre de propriété',
    taxLabel: segment === 'commune' ? 'HT' : 'TTC',
    budgetLabel:
      segment === 'commune'
        ? 'Budget communal'
        : 'Autofinancement',
  };
}

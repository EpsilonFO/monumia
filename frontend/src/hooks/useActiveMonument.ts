import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAuthStore } from '@/stores/useAuthStore';
import type { Monument } from '@/types';

export function useActiveMonument(): Monument | undefined {
  const activeId = useMonumentStore((s) => s.activeMonumentId);
  const monuments = useMonumentStore((s) => s.monuments);
  const user = useAuthStore((s) => s.user);

  if (activeId) {
    return monuments.find((m) => m.id === activeId);
  }

  // Default to user's first monument
  if (user) {
    return monuments.find((m) => m.userId === user.id);
  }

  return undefined;
}

export function useUserMonuments(): Monument[] {
  const monuments = useMonumentStore((s) => s.monuments);
  const user = useAuthStore((s) => s.user);

  if (!user) return [];
  return monuments.filter((m) => m.userId === user.id);
}

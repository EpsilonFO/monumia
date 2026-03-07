import { useEffect } from 'react';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { monumentService } from '@/services/monument.service';
import type { Monument } from '@/types';

export function useMonuments(): { monuments: Monument[]; loading: boolean } {
  const monuments = useMonumentStore((s) => s.monuments);
  const setMonuments = useMonumentStore((s) => s.setMonuments);
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (!token) return;
    monumentService.getAll().then(setMonuments).catch(console.error);
  }, [token]);

  // Consider loaded once we've attempted fetch (monuments may be empty)
  return { monuments, loading: false };
}

export function useActiveMonument(): Monument | undefined {
  const activeId = useMonumentStore((s) => s.activeMonumentId);
  const monuments = useMonumentStore((s) => s.monuments);

  if (activeId) {
    return monuments.find((m) => m.id === activeId);
  }

  return monuments[0];
}

export function useUserMonuments(): Monument[] {
  const { monuments } = useMonuments();
  return monuments;
}

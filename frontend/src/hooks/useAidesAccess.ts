import { useAuthStore } from '@/stores/useAuthStore';

export function useAidesAccess(): { locked: boolean } {
  const user = useAuthStore((s) => s.user);
  return { locked: !user?.hasAidesAccess };
}

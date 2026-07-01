import type { MerimeeRecord } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const merimeeService = {
  async search(query: string, signal?: AbortSignal): Promise<MerimeeRecord[]> {
    if (!query || query.length < 2) return [];

    try {
      const response = await fetch(
        `${API_BASE}/merimee/search?q=${encodeURIComponent(query)}`,
        { signal }
      );
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async getByReference(reference: string): Promise<MerimeeRecord | undefined> {
    const response = await fetch(
      `${API_BASE}/merimee/${encodeURIComponent(reference)}`
    );
    if (!response.ok) return undefined;
    return response.json();
  },
};

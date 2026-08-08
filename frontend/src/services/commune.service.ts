const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** Commune du référentiel INSEE (table `communes`), telle que renvoyée par l'API. */
export interface CommuneResult {
  codeInsee: string;
  nom: string;
  departement: string;
  codeDepartement: string;
  region: string;
  arrondissement?: string | null;
  population?: number | null;
}

export const communeService = {
  /**
   * Communes dont le nom commence par la saisie, puis celles qui la contiennent.
   * Endpoint public (l'onboarding s'en sert avant l'authentification).
   * Ne jette jamais : une recherche qui échoue ne doit pas bloquer la saisie
   * manuelle du nom de commune.
   */
  async search(query: string, signal?: AbortSignal): Promise<CommuneResult[]> {
    if (!query || query.trim().length < 2) return [];
    try {
      const response = await fetch(
        `${API_BASE}/communes/search?q=${encodeURIComponent(query)}&limit=8`,
        { signal },
      );
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },
};

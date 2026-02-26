import type { MerimeeRecord } from '@/types';
import { mockMerimeeRecords } from '@/data/mock-merimee';

export const merimeeService = {
  search(query: string): MerimeeRecord[] {
    if (!query || query.length < 2) return [];

    const q = query.toLowerCase();
    return mockMerimeeRecords.filter(
      (r) =>
        r.denomination.toLowerCase().includes(q) ||
        r.commune.toLowerCase().includes(q) ||
        r.reference.toLowerCase().includes(q) ||
        r.adresse.toLowerCase().includes(q) ||
        r.description.toLowerCase().includes(q)
    );
  },

  getByReference(reference: string): MerimeeRecord | undefined {
    return mockMerimeeRecords.find((r) => r.reference === reference);
  },

  getByCommune(commune: string): MerimeeRecord[] {
    const c = commune.toLowerCase();
    return mockMerimeeRecords.filter((r) => r.commune.toLowerCase() === c);
  },

  getByDepartement(departement: string): MerimeeRecord[] {
    return mockMerimeeRecords.filter((r) => r.departement === departement);
  },
};

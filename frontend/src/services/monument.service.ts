import type { Monument, MonumentPhoto } from '@/types';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { generateId } from '@/lib/format-utils';

export const monumentService = {
  getAll(): Monument[] {
    return useMonumentStore.getState().monuments;
  },

  getById(id: string): Monument | undefined {
    return useMonumentStore.getState().getMonument(id);
  },

  getByUser(userId: string): Monument[] {
    return useMonumentStore.getState().getMonumentsByUser(userId);
  },

  create(data: Omit<Monument, 'id' | 'createdAt' | 'updatedAt' | 'completionPercentage' | 'photos'>): Monument {
    const now = new Date().toISOString();
    const monument: Monument = {
      ...data,
      id: `mon-${generateId()}`,
      photos: [],
      completionPercentage: calculateCompletion(data),
      createdAt: now,
      updatedAt: now,
    };
    useMonumentStore.getState().addMonument(monument);
    return monument;
  },

  update(id: string, updates: Partial<Monument>): void {
    const current = useMonumentStore.getState().getMonument(id);
    if (!current) return;

    const merged = { ...current, ...updates };
    const completionPercentage = calculateCompletion(merged);
    useMonumentStore.getState().updateMonument(id, {
      ...updates,
      completionPercentage,
    });
  },

  delete(id: string): void {
    useMonumentStore.getState().deleteMonument(id);
  },

  addPhoto(monumentId: string, photo: Omit<MonumentPhoto, 'id'>): void {
    useMonumentStore.getState().addPhoto(monumentId, {
      ...photo,
      id: `ph-${generateId()}`,
    });
  },

  removePhoto(monumentId: string, photoId: string): void {
    useMonumentStore.getState().removePhoto(monumentId, photoId);
  },
};

function calculateCompletion(data: Partial<Monument>): number {
  let filled = 0;
  let total = 0;

  // Step 1: Identification (5 fields)
  const step1Fields = ['nom', 'denomination', 'adresse', 'commune', 'region'] as const;
  step1Fields.forEach((f) => {
    total++;
    if (data[f]) filled++;
  });

  // Step 2: Legal (2 fields)
  const step2Fields = ['protection', 'proprietaire'] as const;
  step2Fields.forEach((f) => {
    total++;
    if (data[f]) filled++;
  });

  // Step 3: Physical (3 fields)
  const step3Fields = ['siecleConstruction', 'materiaux', 'descriptionGenerale'] as const;
  step3Fields.forEach((f) => {
    total++;
    if (data[f]) filled++;
  });

  // Step 4: State (2 fields)
  const step4Fields = ['etatConservation', 'travauxEnvisages'] as const;
  step4Fields.forEach((f) => {
    total++;
    if (data[f]) filled++;
  });

  // Step 5: Photos
  total++;
  if (data.photos && data.photos.length > 0) filled++;

  return total > 0 ? Math.round((filled / total) * 100) : 0;
}

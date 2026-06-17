import { create } from 'zustand';
import type { Template } from '@/types';
import { templateService } from '@/services/template.service';

interface TemplateState {
  templates: Template[];
  loaded: boolean;
  loading: boolean;
  error: string | null;

  /** Load the full library once (referential dataset, cached in the store). */
  fetchAll: () => Promise<void>;
}

export const useTemplateStore = create<TemplateState>()((set, get) => ({
  templates: [],
  loaded: false,
  loading: false,
  error: null,

  fetchAll: async () => {
    if (get().loading) return;
    set({ loading: true, error: null });
    try {
      const templates = await templateService.getAll();
      set({ templates, loaded: true, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },
}));

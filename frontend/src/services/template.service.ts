import { supabase } from '@/lib/supabase';
import { authFetch, handleResponse } from '@/lib/auth-fetch';
import type { Template } from '@/types';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const STORAGE_BUCKET = 'templates';

function toTemplate(row: Record<string, unknown>): Template {
  return {
    id: row.id as string,
    slug: row.slug as string,
    nom: row.nom as string,
    description: (row.description as string | null) ?? undefined,
    typeDocument: row.typeDocument as string,
    tags: (row.tags as string[]) ?? [],
    categoriesAide: (row.categoriesAide as string[]) ?? [],
    organisme: (row.organisme as string | null) ?? undefined,
    fichierUrl: row.fichierUrl as string,
    nomFichier: row.nomFichier as string,
    extension: (row.extension as string | null) ?? undefined,
    mimeType: (row.mimeType as string | null) ?? undefined,
    tailleFichier: (row.tailleFichier as number | null) ?? undefined,
    sourceUrl: (row.sourceUrl as string | null) ?? undefined,
    createdAt: (row.createdAt as string | null) ?? undefined,
    updatedAt: (row.updatedAt as string | null) ?? undefined,
  };
}

/** Public URL of a template file (the `templates` bucket is public). */
function getPublicUrl(storagePath: string): string {
  return supabase.storage.from(STORAGE_BUCKET).getPublicUrl(storagePath).data.publicUrl;
}

/** Trigger a browser download of a template file. */
function download(template: Template): void {
  const url = getPublicUrl(template.fichierUrl);
  const a = document.createElement('a');
  a.href = url;
  a.download = template.nomFichier;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export const templateService = {
  async getAll(params?: { categorie?: string; type?: string }): Promise<Template[]> {
    const url = new URL(`${BASE}/templates`);
    if (params?.categorie) url.searchParams.set('categorie', params.categorie);
    if (params?.type) url.searchParams.set('type', params.type);

    const res = await authFetch(url.toString());
    const rows = await handleResponse<Record<string, unknown>[]>(res);
    return rows.map(toTemplate);
  },

  getPublicUrl,
  download,
};

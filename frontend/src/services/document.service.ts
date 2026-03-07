import { supabase } from '@/lib/supabase';
import { useAuthStore } from '@/stores/useAuthStore';
import type { Document, DocumentType } from '@/types';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const STORAGE_BUCKET = 'documents';

function authHeaders() {
  const token = useAuthStore.getState().token;
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function uploadToStorage(file: File, userId: string): Promise<string> {
  const ext = file.name.split('.').pop() ?? 'bin';
  const path = `${userId}/${Date.now()}_${Math.random().toString(36).slice(2)}.${ext}`;

  // Inject the JWT so Supabase Storage honours RLS policies
  const token = useAuthStore.getState().token;
  if (token) {
    await supabase.auth.setSession({ access_token: token, refresh_token: token });
  }

  const { error } = await supabase.storage
    .from(STORAGE_BUCKET)
    .upload(path, file, { upsert: false });

  if (error) throw new Error(`Erreur upload fichier : ${error.message}`);

  const { data } = supabase.storage.from(STORAGE_BUCKET).getPublicUrl(path);
  return data.publicUrl;
}

export interface UploadDocumentPayload {
  file: File;
  nom: string;
  type: DocumentType | 'autre';
  monumentId?: string;
  description?: string;
  tags?: string[];
}

function toDocument(row: Record<string, unknown>): Document {
  return {
    id: row.id as string,
    nom: row.nom as string,
    nomFichier: row.nom_fichier as string,
    type: row.type as DocumentType,
    tags: (row.tags as string[]) ?? [],
    tailleFichier: row.taille_fichier as number,
    mimeType: row.mime_type as string,
    url: row.url as string,
    dossiersUtilises: (row.dossiers_utilises as string[]) ?? [],
    userId: row.user_id as string,
    monumentId: row.monument_id as string | undefined,
    dateUpload: row.date_upload as string,
    dateDocument: row.date_document as string | undefined,
    description: row.description as string | undefined,
  };
}

export const documentService = {
  async getAll(params?: { monumentId?: string; type?: string }): Promise<Document[]> {
    const url = new URL(`${BASE}/documents`);
    if (params?.monumentId) url.searchParams.set('monument_id', params.monumentId);
    if (params?.type) url.searchParams.set('type', params.type);

    const res = await fetch(url.toString(), { headers: authHeaders() });
    const rows = await handleResponse<Record<string, unknown>[]>(res);
    return rows.map(toDocument);
  },

  async getById(id: string): Promise<Document> {
    const res = await fetch(`${BASE}/documents/${id}`, { headers: authHeaders() });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  async upload(payload: UploadDocumentPayload, userId: string): Promise<Document> {
    const url = await uploadToStorage(payload.file, userId);

    const body = {
      nom: payload.nom,
      nom_fichier: payload.file.name,
      type: payload.type || 'autre',
      tags: payload.tags ?? [],
      taille_fichier: payload.file.size,
      mime_type: payload.file.type,
      url,
      monument_id: payload.monumentId ?? null,
      description: payload.description ?? null,
    };

    const res = await fetch(`${BASE}/documents`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  async update(id: string, updates: { nom?: string; type?: string; description?: string; tags?: string[] }): Promise<Document> {
    const res = await fetch(`${BASE}/documents/${id}`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(updates),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  async delete(id: string): Promise<void> {
    const res = await fetch(`${BASE}/documents/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!res.ok && res.status !== 204) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
  },

  async linkToDossier(documentId: string, dossierId: string): Promise<void> {
    const res = await fetch(`${BASE}/documents/${documentId}/link/${dossierId}`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!res.ok && res.status !== 204) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
  },

  async unlinkFromDossier(documentId: string, dossierId: string): Promise<void> {
    const res = await fetch(`${BASE}/documents/${documentId}/link/${dossierId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!res.ok && res.status !== 204) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
  },
};

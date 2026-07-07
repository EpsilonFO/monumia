import { supabase } from '@/lib/supabase';
import { useAuthStore } from '@/stores/useAuthStore';
import { authFetch, handleResponse } from '@/lib/auth-fetch';
import { ensureFreshAccessToken } from '@/lib/token-refresh';
import type { Document, DocumentType, DocumentVisibility } from '@/types';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const STORAGE_BUCKET = 'documents';

/**
 * Extract the storage path from a value that may be a full Supabase public URL
 * or already a relative path.
 * e.g. "https://xxx.supabase.co/storage/v1/object/public/documents/userId/file.pdf"
 *   → "userId/file.pdf"
 */
function toStoragePath(urlOrPath: string): string {
  const marker = `/storage/v1/object/public/${STORAGE_BUCKET}/`;
  const idx = urlOrPath.indexOf(marker);
  if (idx !== -1) return decodeURIComponent(urlOrPath.slice(idx + marker.length));
  return urlOrPath;
}

let sessionSyncPromise: Promise<void> | null = null;

/**
 * Inject the current access_token into the Supabase JS client so storage
 * operations carry an Authorization header. Refreshes the token via the
 * backend first if it's expired. Deduplicated to prevent racing setSession
 * calls (e.g. an upload + signed-URL fetch happening concurrently).
 *
 * The Supabase client itself has autoRefreshToken/persistSession disabled
 * (see lib/supabase.ts), so setSession is now a pure local-state write.
 */
async function syncSupabaseSession(): Promise<void> {
  if (sessionSyncPromise) return sessionSyncPromise;
  sessionSyncPromise = (async () => {
    const fresh = await ensureFreshAccessToken();
    if (!fresh) return;
    const { token } = useAuthStore.getState();
    if (!token) return;
    await supabase.auth.setSession({
      access_token: token,
      // Jamais utilisé (autoRefreshToken désactivé, token frais garanti par
      // ensureFreshAccessToken) mais setSession exige une valeur non vide.
      refresh_token: 'cookie-managed',
    });
  })().finally(() => {
    sessionSyncPromise = null;
  });
  return sessionSyncPromise;
}

async function uploadToStorage(file: File, userId: string): Promise<string> {
  const ext = file.name.split('.').pop() ?? 'bin';
  const path = `${userId}/${Date.now()}_${Math.random().toString(36).slice(2)}.${ext}`;

  await syncSupabaseSession();

  const { error } = await supabase.storage
    .from(STORAGE_BUCKET)
    .upload(path, file, { upsert: false });

  if (error) throw new Error(`Erreur upload fichier : ${error.message}`);

  // Store the storage path, not a public URL — the bucket is private
  return path;
}

export interface UploadDocumentPayload {
  file: File;
  nom: string;
  type: DocumentType | 'autre';
  monumentId?: string;
  monumentIds?: string[];
  description?: string;
  tags?: string[];
  visibility?: DocumentVisibility;
  allowedUserIds?: string[];
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
    url: toStoragePath(row.url as string),
    dossiersUtilises: (row.dossiers_utilises as string[]) ?? [],
    userId: row.user_id as string,
    monumentIds: (row.monument_ids as string[]) ?? [],
    dateUpload: row.date_upload as string,
    dateDocument: row.date_document as string | undefined,
    description: row.description as string | undefined,
    visibility: (row.visibility as DocumentVisibility) ?? 'team',
    allowedUserIds: (row.allowed_user_ids as string[]) ?? [],
    trashedAt: (row.trashed_at as string | null) ?? undefined,
  };
}

/**
 * URL signée d'un document, générée par le backend (client service-role).
 * Permet à tout membre d'un projet du document de le consulter — la signature
 * directe côté client est bloquée par la RLS storage (dossier du dépositaire).
 */
async function getSignedUrl(documentId: string): Promise<string> {
  const res = await authFetch(`${BASE}/documents/${documentId}/signed-url`);
  const data = await handleResponse<{ signed_url: string }>(res);
  return data.signed_url;
}

export const documentService = {
  async getAll(params?: { monumentId?: string; type?: string; trashed?: boolean }): Promise<Document[]> {
    const url = new URL(`${BASE}/documents`);
    if (params?.monumentId) url.searchParams.set('monument_id', params.monumentId);
    if (params?.type) url.searchParams.set('type', params.type);
    if (params?.trashed) url.searchParams.set('trashed', 'true');

    const res = await authFetch(url.toString());
    const rows = await handleResponse<Record<string, unknown>[]>(res);
    return rows.map(toDocument);
  },

  async getById(id: string): Promise<Document> {
    const res = await authFetch(`${BASE}/documents/${id}`);
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  async upload(payload: UploadDocumentPayload, userId: string): Promise<Document> {
    const url = await uploadToStorage(payload.file, userId);

    // Build monument_ids from either monumentIds array or single monumentId
    const monumentIds = payload.monumentIds ?? (payload.monumentId ? [payload.monumentId] : []);

    const body = {
      nom: payload.nom,
      nom_fichier: payload.file.name,
      type: payload.type || 'autre',
      tags: payload.tags ?? [],
      taille_fichier: payload.file.size,
      mime_type: payload.file.type,
      url,
      monument_ids: monumentIds,
      description: payload.description ?? null,
      visibility: payload.visibility ?? null,
      allowed_user_ids: payload.allowedUserIds ?? [],
    };

    const res = await authFetch(`${BASE}/documents`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  async update(
    id: string,
    updates: {
      nom?: string;
      type?: string;
      description?: string;
      tags?: string[];
      visibility?: DocumentVisibility;
      allowedUserIds?: string[];
    },
  ): Promise<Document> {
    const body: Record<string, unknown> = { ...updates };
    if (updates.allowedUserIds !== undefined) {
      body.allowed_user_ids = updates.allowedUserIds;
      delete body.allowedUserIds;
    }
    const res = await authFetch(`${BASE}/documents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  async delete(id: string): Promise<void> {
    const res = await authFetch(`${BASE}/documents/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok && res.status !== 204) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
  },

  async addToProjects(documentId: string, monumentIds: string[]): Promise<Document> {
    const res = await authFetch(`${BASE}/documents/${documentId}/projects`, {
      method: 'POST',
      body: JSON.stringify({ monument_ids: monumentIds }),
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  async linkToDossier(documentId: string, dossierId: string): Promise<void> {
    const res = await authFetch(`${BASE}/documents/${documentId}/link/${dossierId}`, {
      method: 'POST',
    });
    if (!res.ok && res.status !== 204) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
  },

  async unlinkFromDossier(documentId: string, dossierId: string): Promise<void> {
    const res = await authFetch(`${BASE}/documents/${documentId}/link/${dossierId}`, {
      method: 'DELETE',
    });
    if (!res.ok && res.status !== 204) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
  },

  async trash(id: string): Promise<Document> {
    const res = await authFetch(`${BASE}/documents/${id}/trash`, { method: 'POST' });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  async restore(id: string): Promise<Document> {
    const res = await authFetch(`${BASE}/documents/${id}/restore`, { method: 'POST' });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  async removeFromProject(id: string, monumentId: string): Promise<Document> {
    const res = await authFetch(`${BASE}/documents/${id}/projects/${monumentId}`, {
      method: 'DELETE',
    });
    const row = await handleResponse<Record<string, unknown>>(res);
    return toDocument(row);
  },

  getSignedUrl,
};

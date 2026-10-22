import i18n from '@/i18n';
import { getSupabase } from '@/lib/supabase';
import { useAuthStore } from '@/stores/useAuthStore';
import { ensureFreshAccessToken } from '@/lib/token-refresh';

/** Bucket privé unique : documents ET photos de monument y vivent côte à côte. */
export const STORAGE_BUCKET = 'documents';

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
export async function syncSupabaseSession(): Promise<void> {
  if (sessionSyncPromise) return sessionSyncPromise;
  sessionSyncPromise = (async () => {
    const fresh = await ensureFreshAccessToken();
    if (!fresh) return;
    const { token } = useAuthStore.getState();
    if (!token) return;
    await getSupabase().auth.setSession({
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

/**
 * Dépose un fichier dans le bucket privé, sous le dossier de l'utilisateur.
 *
 * Rend le CHEMIN de stockage, jamais une URL publique : le bucket est privé et
 * la lecture passe toujours par un lien signé côté serveur. Le backend refuse
 * d'ailleurs tout chemin qui ne commence pas par `<user_id>/`.
 */
export async function uploadToStorage(file: File, userId: string): Promise<string> {
  const ext = file.name.split('.').pop() ?? 'bin';
  const path = `${userId}/${Date.now()}_${Math.random().toString(36).slice(2)}.${ext}`;

  await syncSupabaseSession();

  const { error } = await getSupabase().storage
    .from(STORAGE_BUCKET)
    .upload(path, file, { upsert: false });

  if (error) throw new Error(i18n.t('core:storageUpload.erreur', { message: error.message }));

  return path;
}

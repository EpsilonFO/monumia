import { createClient, type SupabaseClient } from '@supabase/supabase-js';

let client: SupabaseClient | null = null;

/**
 * Client Supabase, créé au PREMIER USAGE et non au chargement du module.
 *
 * Même discipline que `db.py` côté backend : importer un module ne doit jamais
 * exiger de configuration. `createClient` lève « supabaseUrl is required »
 * quand la variable manque, donc l'appeler au niveau module faisait échouer
 * l'import de toute la chaîne qui en dépend (service → store → composant). En
 * CI, où aucun `.env` n'est fourni parce qu'aucun test ne joint Supabase, le
 * seul import de `useAuthStore` suffisait à faire tomber une suite entière.
 *
 * The backend (FastAPI) is the source of truth for auth. We disable the
 * Supabase JS client's own session management to prevent it from silently
 * rotating the refresh_token in the background — which would invalidate the
 * token we keep in Zustand and break our /auth/refresh flow.
 */
export function getSupabase(): SupabaseClient {
  if (client) return client;
  // Accès littéraux : Vite ne substitue `import.meta.env.X` qu'écrit en clair.
  // Une lecture par clé dynamique renverrait undefined une fois bundlé.
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
  const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      'VITE_SUPABASE_URL et VITE_SUPABASE_ANON_KEY sont requis pour joindre Supabase. '
        + 'Renseignez-les dans frontend/.env.local.',
    );
  }
  client = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
      detectSessionInUrl: false,
    },
  });
  return client;
}

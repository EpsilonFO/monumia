import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

// The backend (FastAPI) is the source of truth for auth. We disable the
// Supabase JS client's own session management to prevent it from silently
// rotating the refresh_token in the background — which would invalidate the
// token we keep in Zustand and break our /auth/refresh flow.
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: false,
    persistSession: false,
    detectSessionInUrl: false,
  },
});

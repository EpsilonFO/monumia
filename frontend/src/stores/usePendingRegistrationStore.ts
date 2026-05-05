import { create } from 'zustand';

// In-memory only: never persisted to localStorage / sessionStorage. The
// credentials are wiped on tab close, page reload, or after the registration
// call finishes. We previously kept the password in sessionStorage, which
// any XSS or browser extension could read in cleartext.
interface PendingRegistrationState {
  email: string | null;
  password: string | null;
  setCredentials: (email: string, password: string) => void;
  clear: () => void;
  has: () => boolean;
}

export const usePendingRegistrationStore = create<PendingRegistrationState>()((set, get) => ({
  email: null,
  password: null,
  setCredentials: (email, password) => set({ email, password }),
  clear: () => set({ email: null, password: null }),
  has: () => Boolean(get().email && get().password),
}));

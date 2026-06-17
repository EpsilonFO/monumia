/**
 * Cross-app helpers shared between the application (app.<domain>) and the
 * public landing page (apex <domain>), which are two separate origins.
 *
 * Because localStorage is isolated per-origin, the landing page cannot read the
 * app's auth store. Instead, the app drops a small non-sensitive "session hint"
 * cookie scoped to the parent domain (e.g. `.monumia.fr`) so the landing can
 * show a "Tableau de bord" button when the user is already logged in.
 *
 * The cookie holds no token — only a boolean presence flag.
 */

const SESSION_COOKIE = 'monumia_session';

/** Apex domain (`monumia.fr`, `patrialta.fr`, …) or `null` on localhost/IP. */
function apexDomain(): string | null {
  const host = window.location.hostname;
  if (host === 'localhost' || /^[\d.]+$/.test(host)) return null;
  const parts = host.split('.');
  if (parts.length < 2) return null;
  return parts.slice(-2).join('.');
}

/** URL of the public landing page, derived from the current host. */
export function landingUrl(): string {
  const fromEnv = import.meta.env.VITE_LANDING_URL as string | undefined;
  if (fromEnv) return fromEnv;

  const { protocol, hostname } = window.location;
  // Dev: landing runs on port 3001 alongside the app on 3000.
  if (hostname === 'localhost' || /^[\d.]+$/.test(hostname)) {
    return `${protocol}//${hostname}:3001`;
  }
  return `${protocol}//${apexDomain()}`;
}

/** Mark the cross-domain session as active. Called on login / rehydration. */
export function setSessionCookie(): void {
  const apex = apexDomain();
  const domain = apex ? `; domain=.${apex}` : '';
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  const maxAge = 60 * 60 * 24 * 30; // 30 days
  document.cookie = `${SESSION_COOKIE}=1; path=/; max-age=${maxAge}; SameSite=Lax${domain}${secure}`;
}

/** Clear the cross-domain session hint. Called on logout. */
export function clearSessionCookie(): void {
  const apex = apexDomain();
  const domain = apex ? `; domain=.${apex}` : '';
  document.cookie = `${SESSION_COOKIE}=; path=/; max-age=0; SameSite=Lax${domain}`;
}

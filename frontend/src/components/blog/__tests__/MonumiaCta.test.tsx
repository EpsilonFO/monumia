import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// État mutable partagé avec le mock (vi.mock est hoisté, d'où vi.hoisted).
const authState = vi.hoisted(() => ({
  user: null as { id: string } | null,
  token: null as string | null,
}));

vi.mock('@/stores/useAuthStore', () => ({
  useAuthStore: (selector: (s: typeof authState) => unknown) => selector(authState),
}));

import { MonumiaCta } from '../MonumiaCta';

function render(): string {
  return renderToStaticMarkup(
    createElement(MemoryRouter, null, createElement(MonumiaCta)),
  );
}

describe('MonumiaCta', () => {
  beforeEach(() => {
    authState.user = null;
    authState.token = null;
  });

  it('rend l’encadré CTA pour un visiteur déconnecté', () => {
    const html = render();
    expect(html).toContain('Découvrir Monumia');
    expect(html).toContain('href="/login"');
    expect(html).toContain('Un projet sur un bien protégé');
  });

  it('ne rend rien pour un utilisateur connecté', () => {
    authState.user = { id: 'u1' };
    authState.token = 'jwt-token';
    expect(render()).toBe('');
  });

  it('rend le CTA si le token manque (session incomplète = déconnecté)', () => {
    authState.user = { id: 'u1' };
    authState.token = null;
    expect(render()).toContain('Découvrir Monumia');
  });
});

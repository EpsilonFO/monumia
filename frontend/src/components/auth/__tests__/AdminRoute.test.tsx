import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// État mutable partagé avec le mock (vi.mock est hoisté, d'où vi.hoisted).
const authState = vi.hoisted(() => ({
  user: null as { id: string; estAdmin?: boolean } | null,
}));

vi.mock('@/stores/useAuthStore', () => ({
  useAuthStore: (selector: (s: typeof authState) => unknown) => selector(authState),
}));

import { AdminRoute } from '../AdminRoute';

function render(): string {
  return renderToStaticMarkup(
    createElement(
      MemoryRouter,
      null,
      createElement(AdminRoute, null, createElement('p', null, 'Administration du catalogue')),
    ),
  );
}

describe('AdminRoute', () => {
  beforeEach(() => {
    authState.user = null;
  });

  it('ne rend pas la page à un visiteur sans profil', () => {
    expect(render()).toBe('');
  });

  it('ne rend pas la page à un compte ordinaire', () => {
    authState.user = { id: 'u1' };
    expect(render()).toBe('');
  });

  it('ne rend pas la page quand estAdmin est faux', () => {
    authState.user = { id: 'u1', estAdmin: false };
    expect(render()).toBe('');
  });

  it('rend la page à un administrateur', () => {
    authState.user = { id: 'u1', estAdmin: true };
    expect(render()).toContain('Administration du catalogue');
  });
});

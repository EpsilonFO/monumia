import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  clePostHog,
  nettoyerChaine,
  nettoyerEvenement,
  nettoyerUrl,
} from '@/lib/mesure-audience';

const MONUMENT = '3f2b8c1e-9a4d-4e7f-b1c2-0d5e6f7a8b9c';
const PROJET = 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d';
const JETON = 'Xk3_vQ9-zLmN2pRtY7wE4sA1bC8dF6gH0jK5';

describe('clePostHog', () => {
  afterEach(() => vi.unstubAllEnvs());

  it('rend undefined sans variable : la mesure ne démarre pas', () => {
    vi.stubEnv('VITE_POSTHOG_KEY', '');
    expect(clePostHog()).toBeUndefined();
  });

  it('rend undefined pour une valeur faite de blancs', () => {
    vi.stubEnv('VITE_POSTHOG_KEY', '   ');
    expect(clePostHog()).toBeUndefined();
  });

  it('rend la clé, sans les blancs autour', () => {
    vi.stubEnv('VITE_POSTHOG_KEY', ' phc_abc ');
    expect(clePostHog()).toBe('phc_abc');
  });
});

describe('nettoyerChaine', () => {
  it('remplace les identifiants de monument et de projet', () => {
    expect(nettoyerChaine(`/app/monuments/${MONUMENT}/projets/nouveau`)).toBe(
      '/app/monuments/:id/projets/nouveau',
    );
    expect(nettoyerChaine(`/app/projets/${PROJET}/dossiers/${MONUMENT}`)).toBe(
      '/app/projets/:id/dossiers/:id',
    );
  });

  it("retire le jeton d'invitation, qui vaut accès", () => {
    expect(nettoyerChaine(`/invitation/${JETON}`)).toBe('/invitation/:jeton');
  });

  it('retire les adresses email', () => {
    expect(nettoyerChaine('mailto:camille.durand@exemple.fr')).toBe('mailto::email');
  });

  it('garde les slugs des aides, publics', () => {
    expect(nettoyerChaine(`/app/projets/${PROJET}/aides/drac-monuments-historiques`)).toBe(
      '/app/projets/:id/aides/drac-monuments-historiques',
    );
  });
});

describe('nettoyerUrl', () => {
  it("ne garde que le paramètre d'onglet", () => {
    expect(
      nettoyerUrl(`https://app.monumia.fr/app/monuments/${MONUMENT}?tab=equipe&projet=${PROJET}`),
    ).toBe('https://app.monumia.fr/app/monuments/:id?tab=equipe');
  });

  it('retire le code du retour Google et le jeton Supabase du fragment', () => {
    expect(nettoyerUrl('https://app.monumia.fr/auth/callback?code=abc123')).toBe(
      'https://app.monumia.fr/auth/callback',
    );
    expect(
      nettoyerUrl('https://app.monumia.fr/reset-password#access_token=eyJ.secret&type=recovery'),
    ).toBe('https://app.monumia.fr/reset-password');
  });

  it('retire la session Stripe du retour de paiement', () => {
    expect(nettoyerUrl('https://app.monumia.fr/tarifs?session_id=cs_test_123')).toBe(
      'https://app.monumia.fr/tarifs',
    );
  });

  it('garde un chemin relatif relatif', () => {
    expect(nettoyerUrl(`/app/projets/${PROJET}?tab=aides`)).toBe('/app/projets/:id?tab=aides');
  });

  it("laisse passer ce qui n'est pas une adresse", () => {
    expect(nettoyerUrl('$direct')).toBe('$direct');
  });
});

describe('nettoyerEvenement', () => {
  it("ne laisse rien partir d'un compte administrateur", () => {
    const evenement = { event: '$pageview', properties: {} };
    expect(nettoyerEvenement(evenement, true)).toBeNull();
  });

  it('laisse tomber un événement déjà écarté', () => {
    expect(nettoyerEvenement(null, false)).toBeNull();
  });

  it("nettoie les propriétés d'une page vue", () => {
    const sortie = nettoyerEvenement(
      {
        event: '$pageview',
        properties: {
          $current_url: `https://app.monumia.fr/invitation/${JETON}?ref=email`,
          $pathname: `/invitation/${JETON}`,
          $referrer: `https://app.monumia.fr/app/monuments/${MONUMENT}?tab=projets`,
          $host: 'app.monumia.fr',
          $browser: 'Firefox',
        },
      },
      false,
    );
    expect(sortie?.properties).toEqual({
      $current_url: 'https://app.monumia.fr/invitation/:jeton',
      $pathname: '/invitation/:jeton',
      $referrer: 'https://app.monumia.fr/app/monuments/:id?tab=projets',
      $host: 'app.monumia.fr',
      $browser: 'Firefox',
    });
  });

  it('nettoie les liens des éléments cliqués', () => {
    const sortie = nettoyerEvenement(
      {
        event: '$autocapture',
        properties: {
          $elements_chain: `a:href="/app/projets/${PROJET}?tab=aides&x=1"nth-child="2"`,
          $elements: [{ tag_name: 'a', attr__href: `mailto:camille@exemple.fr` }],
        },
      },
      false,
    );
    expect(sortie?.properties.$elements_chain).toBe(
      'a:href="/app/projets/:id?tab=aides"nth-child="2"',
    );
    expect(sortie?.properties.$elements).toEqual([{ tag_name: 'a', attr__href: 'mailto::email' }]);
  });

  it('nettoie les URL rangées en clés par les heatmaps', () => {
    const sortie = nettoyerEvenement(
      {
        event: '$$heatmap',
        properties: {
          $heatmap_data: {
            [`https://app.monumia.fr/app/monuments/${MONUMENT}?tab=equipe`]: [{ x: 1, y: 2 }],
          },
        },
      },
      false,
    );
    expect(sortie?.properties.$heatmap_data).toEqual({
      'https://app.monumia.fr/app/monuments/:id?tab=equipe': [{ x: 1, y: 2 }],
    });
  });

  it('garde les propriétés des événements métier', () => {
    const sortie = nettoyerEvenement(
      { event: 'aide_suivie', properties: { aide: 'fondation-patrimoine', statut: 'en_cours' } },
      false,
    );
    expect(sortie?.properties).toEqual({ aide: 'fondation-patrimoine', statut: 'en_cours' });
  });
});

import { describe, it, expect } from 'vitest';
import {
  allowedVisibilities,
  canEditVisibility,
  canViewDocument,
  customIdsForPreset,
  whoCanView,
} from '@/lib/document-visibility';

const doc = (visibility: 'team' | 'responsables' | 'custom', allowedUserIds: string[] = [], userId = 'u2') =>
  ({ visibility, allowedUserIds, userId });

describe('allowedVisibilities', () => {
  it('responsable a les 3 options', () => {
    expect(allowedVisibilities('owner')).toEqual(['team', 'responsables', 'custom']);
    expect(allowedVisibilities('co_owner')).toEqual(['team', 'responsables', 'custom']);
  });
  it('collaborateur (ou null) : pas de toute l\'equipe', () => {
    expect(allowedVisibilities('member')).toEqual(['responsables', 'custom']);
    expect(allowedVisibilities(null)).toEqual(['responsables', 'custom']);
  });
});

describe('canEditVisibility', () => {
  it("l'auteur peut toujours", () => {
    expect(canEditVisibility(true, 'member')).toBe(true);
    expect(canEditVisibility(true, null)).toBe(true);
  });
  it('responsable peut sur tout doc', () => {
    expect(canEditVisibility(false, 'co_owner')).toBe(true);
    expect(canEditVisibility(false, 'owner')).toBe(true);
  });
  it("un membre ne peut pas sur le doc d'un autre", () => {
    expect(canEditVisibility(false, 'member')).toBe(false);
    expect(canEditVisibility(false, null)).toBe(false);
  });
});

describe('canViewDocument', () => {
  it("l'auteur et le chef voient toujours", () => {
    expect(canViewDocument(doc('custom', [], 'u1'), 'u1', null)).toBe(true);
    expect(canViewDocument(doc('custom'), 'u1', 'owner')).toBe(true);
  });
  it('non-membre ne voit jamais', () => {
    expect(canViewDocument(doc('team'), 'u1', null)).toBe(false);
  });
  it('team → tout membre ; responsables → adjoint seulement', () => {
    expect(canViewDocument(doc('team'), 'u1', 'member')).toBe(true);
    expect(canViewDocument(doc('responsables'), 'u1', 'member')).toBe(false);
    expect(canViewDocument(doc('responsables'), 'u1', 'co_owner')).toBe(true);
  });
  it('custom → seulement les personnes listees (membres)', () => {
    expect(canViewDocument(doc('custom', ['u1']), 'u1', 'member')).toBe(true);
    expect(canViewDocument(doc('custom', ['u3']), 'u1', 'co_owner')).toBe(false);
    expect(canViewDocument(doc('custom', ['u1']), 'u1', null)).toBe(false);
  });
});

describe('whoCanView', () => {
  const members = [
    { userId: 'owner1', role: 'owner' as const },
    { userId: 'adj1', role: 'co_owner' as const },
    { userId: 'col1', role: 'member' as const },
    { userId: 'col2', role: 'member' as const },
  ];
  it('team → tout le monde', () => {
    expect(whoCanView(members, 'team', []).sort()).toEqual(['adj1', 'col1', 'col2', 'owner1']);
  });
  it('responsables → chef + adjoints', () => {
    expect(whoCanView(members, 'responsables', []).sort()).toEqual(['adj1', 'owner1']);
  });
  it('custom → chef (toujours) + personnes choisies', () => {
    expect(whoCanView(members, 'custom', ['col1']).sort()).toEqual(['col1', 'owner1']);
  });
  it("inclut toujours l'auteur même si la visibilité l'exclurait", () => {
    expect(whoCanView(members, 'responsables', [], 'col2').sort()).toEqual(['adj1', 'col2', 'owner1']);
  });
});

describe('customIdsForPreset', () => {
  const members = [
    { userId: 'owner1', role: 'owner' as const },
    { userId: 'adj1', role: 'co_owner' as const },
    { userId: 'col1', role: 'member' as const },
  ];
  it('depuis team → tous sauf le chef', () => {
    expect(customIdsForPreset('team', members).sort()).toEqual(['adj1', 'col1']);
  });
  it('depuis responsables → les adjoints', () => {
    expect(customIdsForPreset('responsables', members)).toEqual(['adj1']);
  });
  it('depuis custom → vide (on conserve la selection en place)', () => {
    expect(customIdsForPreset('custom', members)).toEqual([]);
  });
});

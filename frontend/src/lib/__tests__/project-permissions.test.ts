import { describe, it, expect } from 'vitest';
import { projectPermissions, canDeleteDocument, sharedRole, isProjectShared } from '@/lib/project-permissions';

describe('projectPermissions', () => {
  it('owner peut tout sauf quitter', () => {
    const p = projectPermissions('owner');
    expect(p.canInvite).toBe(true);
    expect(p.canManageMembers).toBe(true);
    expect(p.canEditProject).toBe(true);
    expect(p.canDeleteAnyDoc).toBe(true);
    expect(p.canDeleteProject).toBe(true);
    expect(p.canLeave).toBe(false);
  });

  it('co_owner : admin sans suppression de projet, peut quitter', () => {
    const p = projectPermissions('co_owner');
    expect(p.canInvite).toBe(true);
    expect(p.canManageMembers).toBe(true);
    expect(p.canEditProject).toBe(true);
    expect(p.canDeleteAnyDoc).toBe(true);
    expect(p.canDeleteProject).toBe(false);
    expect(p.canLeave).toBe(true);
  });

  it('member : lecture + ses documents, peut quitter', () => {
    const p = projectPermissions('member');
    expect(p.canViewMembers).toBe(true);
    expect(p.canInvite).toBe(false);
    expect(p.canManageMembers).toBe(false);
    expect(p.canEditProject).toBe(false);
    expect(p.canDeleteAnyDoc).toBe(false);
    expect(p.canDeleteProject).toBe(false);
    expect(p.canLeave).toBe(true);
  });

  it('null (non membre) : aucun droit', () => {
    const p = projectPermissions(null);
    expect(p.canViewMembers).toBe(false);
    expect(p.canInvite).toBe(false);
    expect(p.canLeave).toBe(false);
  });
});

describe('canDeleteDocument', () => {
  it("seul l'auteur peut supprimer/remplacer son document", () => {
    expect(canDeleteDocument(true)).toBe(true);
  });
  it("quiconque n'est pas l'auteur ne peut pas (même owner/co_owner)", () => {
    expect(canDeleteDocument(false)).toBe(false);
  });
});

describe('sharedRole', () => {
  it('co_owner et member sont des rôles partagés', () => {
    expect(sharedRole('co_owner')).toBe('co_owner');
    expect(sharedRole('member')).toBe('member');
  });
  it('owner n\'est pas une mention partagée', () => {
    expect(sharedRole('owner')).toBeNull();
  });
  it('undefined / null = projet personnel, pas de mention', () => {
    expect(sharedRole(undefined)).toBeNull();
    expect(sharedRole(null)).toBeNull();
  });
});

describe('isProjectShared', () => {
  it('collaborateur (rôle non-owner) => partagé', () => {
    expect(isProjectShared({ myRole: 'member' })).toBe(true);
    expect(isProjectShared({ myRole: 'co_owner' })).toBe(true);
  });
  it('owner seul => non partagé', () => {
    expect(isProjectShared({ myRole: 'owner', memberCount: 1 })).toBe(false);
  });
  it('owner avec plusieurs membres => partagé', () => {
    expect(isProjectShared({ myRole: 'owner', memberCount: 3 })).toBe(true);
  });
  it('repli sur members.length quand memberCount absent', () => {
    expect(isProjectShared({ members: [{}, {}] })).toBe(true);
    expect(isProjectShared({ members: [{}] })).toBe(false);
  });
  it('aucune info => non partagé', () => {
    expect(isProjectShared({})).toBe(false);
  });
});

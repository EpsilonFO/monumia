import { describe, it, expect } from 'vitest';
import { initials, avatarColor, avatarColorByIndex } from '@/lib/avatar-utils';

describe('initials', () => {
  it('combine première lettre du prénom et du nom', () => {
    expect(initials('Anne', 'Roy')).toBe('AR');
  });
  it('prénom seul => une lettre', () => {
    expect(initials('Anne', '')).toBe('A');
  });
  it('repli sur le fallback (email) si pas de nom', () => {
    expect(initials('', '', 'jean@x.fr')).toBe('J');
  });
  it('repli ultime sur « ? »', () => {
    expect(initials('', '')).toBe('?');
  });
  it('met en majuscules', () => {
    expect(initials('léo', 'bon')).toBe('LB');
  });
});

describe('avatarColor', () => {
  it('est déterministe pour une même graine', () => {
    expect(avatarColor('u1')).toEqual(avatarColor('u1'));
  });
  it('renvoie des couleurs bg/fg', () => {
    const c = avatarColor('u1');
    expect(typeof c.bg).toBe('string');
    expect(typeof c.fg).toBe('string');
  });
  it('graine vide ne plante pas', () => {
    expect(avatarColor('')).toBeTruthy();
  });
});

describe('avatarColorByIndex', () => {
  it('donne des couleurs distinctes aux premiers membres', () => {
    expect(avatarColorByIndex(0)).not.toEqual(avatarColorByIndex(1));
    expect(avatarColorByIndex(1)).not.toEqual(avatarColorByIndex(2));
  });
  it('boucle au-delà de la taille de la palette', () => {
    expect(avatarColorByIndex(0)).toEqual(avatarColorByIndex(8));
  });
  it('gère un index négatif sans planter', () => {
    expect(avatarColorByIndex(-1)).toBeTruthy();
  });
});

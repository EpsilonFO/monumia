import type { Monument, MonumentPhoto } from '@/types';

/**
 * La photo qui illustre le monument, dans l'ordre : sa photo de profil, à
 * défaut une façade, à défaut le premier cliché déposé.
 *
 * Le repli existe pour les fiches d'avant la photo de profil : dès qu'une est
 * posée, c'est elle qui gagne partout (fiche, cartes, tableau de bord).
 */
export function monumentPhotoProfil(monument: Monument): MonumentPhoto | null {
  const photos = monument.photos ?? [];
  return (
    photos.find((p) => p.type === 'profil') ??
    photos.find((p) => p.type === 'facade') ??
    photos[0] ??
    null
  );
}

/**
 * URL AFFICHABLE de cette photo : le lien signé posé par le backend. Le champ
 * `url` est un chemin dans un bucket privé — l'afficher donnerait une image
 * cassée, d'où le `null` quand la signature manque.
 */
export function monumentPhotoUrl(monument: Monument): string | null {
  return monumentPhotoProfil(monument)?.signedUrl ?? null;
}

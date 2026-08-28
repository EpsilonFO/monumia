/**
 * Résolution des vieux liens `/app/projets/:id`.
 *
 * Avant l'inversion de hiérarchie, un « projet » ÉTAIT un monument : l'id de
 * cette URL désignait donc une ligne `monuments`. Depuis, la même URL désigne
 * un PROJET de travaux. Les liens déjà partis (emails d'invitation,
 * notifications, marque-pages) portent encore des ids de monument, et les deux
 * espaces sont des UUID — impossible de les distinguer par la forme.
 *
 * La seule discrimination possible est donc à l'exécution : demander le projet,
 * et sur 404 demander le monument. Ce module tient la décision, pure et
 * testable ; la page se contente d'exécuter les deux appels.
 */

export type LegacyIdResolution =
  | { kind: 'projet' }
  | { kind: 'monument' }
  | { kind: 'introuvable' };

/**
 * Que faire d'un id trouvé sur `/app/projets/:id`, au vu des deux tentatives.
 *
 * `projetTrouve` prime : c'est le sens actuel de l'URL. Un id qui ne répond ni
 * comme projet ni comme monument est introuvable (supprimé, ou accès perdu) —
 * on ne redirige pas au hasard, on montre l'écran « introuvable ».
 */
export function resolveLegacyProjetId(
  projetTrouve: boolean,
  monumentTrouve: boolean,
): LegacyIdResolution {
  if (projetTrouve) return { kind: 'projet' };
  if (monumentTrouve) return { kind: 'monument' };
  return { kind: 'introuvable' };
}

/**
 * Le texte d'aide d'une question (`help` de facts.yaml), découpé pour
 * l'affichage. Règle d'écriture de l'en-tête de facts.yaml : une ligne vide
 * sépare deux paragraphes, une ligne qui commence par « - » ouvre une puce.
 *
 * Une ligne qui ne commence pas par « - » continue ce qui précède : le
 * paragraphe, ou la dernière puce. Un `help` replié par YAML (`>-`) arrive sans
 * retour à la ligne et donne donc un seul paragraphe, exactement comme avant.
 */
export type BlocTexteAide = { type: 'p'; texte: string } | { type: 'ul'; puces: string[] };

const PUCE = /^-\s+/;

export function blocsTexteAide(texte: string | null | undefined): BlocTexteAide[] {
  const blocs: BlocTexteAide[] = [];
  for (const paragraphe of (texte ?? '').split(/\n\s*\n/)) {
    let courant: BlocTexteAide | null = null;
    for (const brute of paragraphe.split('\n')) {
      const ligne = brute.trim();
      if (!ligne) continue;
      if (PUCE.test(ligne)) {
        if (courant?.type !== 'ul') {
          courant = { type: 'ul', puces: [] };
          blocs.push(courant);
        }
        courant.puces.push(ligne.replace(PUCE, ''));
      } else if (courant?.type === 'ul') {
        courant.puces[courant.puces.length - 1] += ` ${ligne}`;
      } else if (courant?.type === 'p') {
        courant.texte += ` ${ligne}`;
      } else {
        courant = { type: 'p', texte: ligne };
        blocs.push(courant);
      }
    }
  }
  return blocs;
}

/** Longueur lue, structure comprise : c'est elle qui décide du repli. */
export function longueurTexteAide(texte: string | null | undefined): number {
  return blocsTexteAide(texte).reduce(
    (n, b) => n + (b.type === 'p' ? b.texte.length : b.puces.join(' ').length),
    0,
  );
}

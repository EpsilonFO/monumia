import { indexDeRecherche, normaliserRecherche } from '@/lib/fiche-monument';

/** Le nom, la partie tapée en `<mark>` (orange de la maquette). */
export function surlignerDebut(brut: string, requete: string) {
  const nom = brut.normalize('NFC');
  const i = indexDeRecherche(nom, requete);
  if (i < 0) return nom;
  const n = normaliserRecherche(requete).replace(/\s+/g, ' ').trim().length;
  return (
    <>
      {nom.slice(0, i)}
      <mark>{nom.slice(i, i + n)}</mark>
      {nom.slice(i + n)}
    </>
  );
}

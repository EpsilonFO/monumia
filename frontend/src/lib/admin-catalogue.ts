/**
 * Logique pure de la page d'administration du catalogue : recherche, fait
 * effectif, et le payload d'une surcharge.
 *
 * Pure et testable en node, comme le reste de `src/lib` : les composants ne
 * décident rien de ce qui suit.
 */

import type { AdminAide, AdminFait, OptionSurchargee, SurchargeFait } from '@/types/admin.types';

/** Minuscules sans accents : on cherche « eglise » et on trouve « Église ». */
export function normaliser(texte: string): string {
  return texte
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim();
}

export function filtrerAides(aides: AdminAide[], recherche: string): AdminAide[] {
  const q = normaliser(recherche);
  if (!q) return aides;
  return aides.filter((aide) =>
    [aide.slug, aide.nom, aide.organisme].some((champ) => normaliser(champ).includes(q)),
  );
}

/**
 * Le fait tel qu'il est POSÉ aujourd'hui : YAML, surcharge appliquée. Même
 * superposition que côté serveur (`surcharger_fait`) — un champ nul veut dire
 * « garder le YAML », et `options`, quand elle est là, remplace la liste.
 */
export function faitEffectif(fait: AdminFait): {
  question: string;
  help: string | null;
  options: OptionSurchargee[];
} {
  const s = fait.surcharge;
  return {
    question: s?.question ?? fait.original.question,
    help: s?.help ?? fait.original.help,
    options: s?.options ?? fait.original.options,
  };
}

export function filtrerFaits(faits: AdminFait[], recherche: string): AdminFait[] {
  const q = normaliser(recherche);
  if (!q) return faits;
  return faits.filter((fait) => {
    const effectif = faitEffectif(fait);
    const champs = [fait.key, effectif.question, ...effectif.options.map((o) => o.label)];
    return champs.some((champ) => normaliser(champ ?? '').includes(q));
  });
}

/**
 * Deux listes de réponses sont-elles la même ? `valeur` en fait partie : sans
 * elle, un brouillon où seule une valeur change passerait pour identique à
 * l'original, la page appellerait DELETE au lieu de PUT et la modification
 * disparaîtrait sans un mot. Miroir de `_options_tuple` côté serveur.
 *
 * Le `?? null` n'est pas cosmétique : `undefined !== null` ferait apparaître
 * une surcharge inutile sur tous les enums, dont les réponses n'ont pas de
 * `valeur` du tout.
 */
function memesOptions(gauche: OptionSurchargee[], droite: OptionSurchargee[]): boolean {
  return (
    gauche.length === droite.length &&
    gauche.every(
      (o, i) =>
        o.id === droite[i].id &&
        o.label === droite[i].label &&
        o.unknown === droite[i].unknown &&
        (o.valeur ?? null) === (droite[i].valeur ?? null),
    )
  );
}

/**
 * Ce qu'il faut envoyer au serveur, ou `null` si le brouillon est revenu à
 * l'original — la page appelle alors DELETE plutôt que PUT.
 *
 * Ne garder que les différences n'est pas une optimisation : une surcharge qui
 * recopie le YAML figerait la formulation, et une correction ultérieure de
 * `facts.yaml` resterait sans effet en production sans que personne comprenne
 * pourquoi. Le serveur applique la même règle, c'est lui qui tranche.
 */
export function payloadSurcharge(
  fait: AdminFait,
  brouillon: { question: string; help: string; options: OptionSurchargee[] },
): SurchargeFait | null {
  const question = brouillon.question.trim();
  const help = brouillon.help.trim();
  const options = brouillon.options.map((o) => ({ ...o, label: o.label.trim() }));

  const payload: SurchargeFait = {
    question: question && question !== fait.original.question ? question : null,
    help: help !== (fait.original.help ?? '') ? help : null,
    options: memesOptions(options, fait.original.options) ? null : options,
  };
  if (payload.question === null && payload.help === null && payload.options === null) return null;
  return payload;
}

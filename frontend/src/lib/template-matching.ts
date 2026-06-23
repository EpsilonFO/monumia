import type { Template } from '@/types';

/**
 * Rapprochement pièce de checklist ↔ modèles de la bibliothèque, par mots-clés.
 *
 * Approche volontairement simple et tolérante au texte libre : on normalise les
 * libellés (sans accents, sans mots-vides) et on compte le recouvrement de
 * tokens entre la pièce et le modèle (nom + tags + type). Une part possiblement
 * élevée des pièces n'a aucun modèle : l'absence de correspondance (`[]`) est un
 * résultat normal.
 */

// Mots-vides français les plus courants — n'apportent aucun signal de matching.
const STOPWORDS = new Set([
  'de', 'du', 'des', 'la', 'le', 'les', 'un', 'une', 'et', 'ou', 'au', 'aux',
  'en', 'sur', 'pour', 'par', 'dans', 'avec', 'sans', 'ce', 'ces', 'se', 'sa',
  'son', 'ses', 'a', 'l', 'd', 'the',
]);

/** Bonus de score quand l'aide cible explicitement la catégorie du modèle. */
const CATEGORY_BONUS = 0.5;

/** Nombre de modèles renvoyés par défaut pour une pièce. */
const DEFAULT_LIMIT = 3;

/**
 * Découpe un texte en tokens signifiants : minuscules, accents retirés, séparé
 * sur tout ce qui n'est pas alphanumérique (gère espaces, apostrophes, tirets,
 * snake_case), mots-vides et tokens d'un seul caractère écartés.
 */
export function normalize(text: string): string[] {
  // Défense : une donnée malformée (label non-chaîne) ne doit pas faire planter
  // le matching (`.normalize` n'existe pas sur un objet).
  if (typeof text !== 'string') return [];
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // diacritiques
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length >= 2 && !STOPWORDS.has(t));
}

function templateTokens(template: Template): Set<string> {
  const tokens = new Set<string>();
  for (const t of normalize(template.nom)) tokens.add(t);
  for (const t of normalize(template.typeDocument)) tokens.add(t);
  for (const tag of template.tags) {
    for (const t of normalize(tag)) tokens.add(t);
  }
  return tokens;
}

/**
 * Score de pertinence d'un modèle pour un libellé de pièce. 0 = aucun token
 * signifiant en commun (les mots-vides seuls ne créent jamais de match). Un
 * bonus s'applique si la catégorie de l'aide figure dans `categoriesAide`.
 */
export function scoreTemplate(template: Template, label: string, categorie?: string): number {
  const haystack = templateTokens(template);
  const labelTokens = new Set(normalize(label));

  let overlap = 0;
  for (const token of labelTokens) {
    if (haystack.has(token)) overlap += 1;
  }
  if (overlap === 0) return 0;

  const categoryMatch =
    categorie && template.categoriesAide.includes(categorie) ? CATEGORY_BONUS : 0;
  return overlap + categoryMatch;
}

/**
 * Modèles pertinents pour une pièce, triés par score décroissant et limités.
 * Renvoie `[]` si rien ne correspond de façon signifiante.
 */
export function matchTemplates(
  templates: Template[],
  label: string,
  categorie?: string,
  limit = DEFAULT_LIMIT,
): Template[] {
  return templates
    .map((template) => ({ template, score: scoreTemplate(template, label, categorie) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((entry) => entry.template);
}

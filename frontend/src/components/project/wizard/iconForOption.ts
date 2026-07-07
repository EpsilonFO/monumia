import {
  IconAide,
  IconCalendrier,
  IconChantier,
  IconCompte,
  IconEquipe,
  IconErreur,
  IconInstitution,
  IconMaison,
  IconMonument,
  IconProtection,
  IconSucces,
  type IconComponent,
} from '@/components/icons';
import type { QcmOption } from '@/types';

/** Minuscules sans diacritiques, pour matcher « Rénovation » avec /renov/. */
function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

/**
 * Mots-clés → icône, testés dans l'ordre (premier match gagne).
 * Oui/Non exigent le début du libellé pour éviter les faux positifs
 * (« sinon », « nonobstant »).
 */
const RULES: Array<[RegExp, IconComponent]> = [
  [/^oui\b/, IconSucces],
  [/^non\b/, IconErreur],
  [/toit|couvertur|charpente|ardoise|tuile|zinc/, IconMaison],
  [/travaux|chantier|restaur|renov|reparat/, IconChantier],
  [/classe|inscrit|protege|protection|patrimonial|abords/, IconProtection],
  [/commune|mairie|departement|region|\betat\b|public/, IconInstitution],
  [/proprietaire|prive|particulier/, IconCompte],
  [/association/, IconEquipe],
  [/date|annee|siecle|avant \d|apres \d/, IconCalendrier],
  [/aide|subvention|financ|budget|euro/, IconAide],
  [/monument|edifice|eglise|chateau|chapelle|batiment/, IconMonument],
];

/**
 * Icône illustrant une option de réponse du QCM (questions générées par le
 * moteur, donc libellés imprévisibles). `null` = pas de correspondance sûre :
 * l'appelant affiche alors une pastille lettrée A/B/C. Ne jette jamais —
 * l'illustration ne doit jamais bloquer l'affichage d'une réponse.
 */
export function iconForOption(option: QcmOption): IconComponent | null {
  const label = normalize(option.label ?? '');
  for (const [re, icon] of RULES) {
    if (re.test(label)) return icon;
  }
  return null;
}

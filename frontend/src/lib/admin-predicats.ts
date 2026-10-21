/**
 * Logique pure de l'onglet Conditions : libellés d'opérateurs, canonisation
 * miroir du serveur, phrase lisible, filtre.
 *
 * Pure et testable en node, comme le reste de `src/lib` : le composant ne
 * décide rien de ce qui suit. La canonisation DOIT rester le miroir exact de
 * `canoniser_predicat` côté serveur — deux canonisations qui divergent, et la
 * page proposerait d'enregistrer un prédicat que le serveur jugerait identique
 * à l'original (donc supprimerait), ou l'inverse.
 */

import i18n from '@/i18n';
import { normaliser } from '@/lib/admin-catalogue';
import type {
  AdminCondition,
  ConditionOrpheline,
  EtatPredicat,
  OperateurPredicat,
} from '@/types/admin.types';

type Operateur = { valeur: OperateurPredicat; label: string; phrase: string };

/** Un opérateur dont le libellé se lit à l'appel, dans la langue de la page. Le
 *  menu et la phrase disent la même chose : une seule clé pour les deux. */
function operateur(valeur: OperateurPredicat, libelle: () => string): Operateur {
  return {
    valeur,
    get label() {
      return libelle();
    },
    get phrase() {
      return libelle();
    },
  };
}

/** Les opérateurs, dans l'ordre d'affichage du menu. `none_in` ne vaut que sur
 *  un choix multiple : cf. `operateursPour`. */
export const OPERATEURS: Operateur[] = [
  operateur('eq', () => i18n.t('admin:predicats.operateurs.eq')),
  operateur('neq', () => i18n.t('admin:predicats.operateurs.neq')),
  operateur('in', () => i18n.t('admin:predicats.operateurs.in')),
  operateur('not_in', () => i18n.t('admin:predicats.operateurs.not_in')),
  operateur('none_in', () => i18n.t('admin:predicats.operateurs.none_in')),
];

/**
 * Sur un choix multiple, le moteur lit `neq` / `not_in` case par case : il
 * suffit qu'UNE case cochée soit hors de la liste (une église qui accueille des
 * concerts « n'est pas cultuelle » à ce compte). Les libellés le disent, pour
 * qu'on ne pose pas une exclusion stricte par erreur ; l'exclusion stricte est
 * `none_in`, absent du menu d'un choix simple où `not_in` dit déjà la même chose.
 */
const MULTIPLE: Partial<Record<OperateurPredicat, Operateur>> = {
  eq: operateur('eq', () => i18n.t('admin:predicats.operateursMultiple.eq')),
  neq: operateur('neq', () => i18n.t('admin:predicats.operateursMultiple.neq')),
  in: operateur('in', () => i18n.t('admin:predicats.operateursMultiple.in')),
  not_in: operateur('not_in', () => i18n.t('admin:predicats.operateursMultiple.not_in')),
};

export function operateursPour(choixMultiple: boolean): Operateur[] {
  if (!choixMultiple) return OPERATEURS.filter((o) => o.valeur !== 'none_in');
  // Le spread lit les getters : les libellés sont figés à l'appel, c'est voulu.
  return OPERATEURS.map((o) => ({ ...o, ...MULTIPLE[o.valeur] }));
}

/** Ce que dit chaque état d'une surcharge, en une ligne, pour l'inventaire. */
export const LIBELLE_ETAT: Record<EtatPredicat, string> = {
  get active() {
    return i18n.t('admin:predicats.etats.active');
  },
  get a_revoir() {
    return i18n.t('admin:predicats.etats.a_revoir');
  },
  get perimee_texte() {
    return i18n.t('admin:predicats.etats.perimee_texte');
  },
  get perimee_fait() {
    return i18n.t('admin:predicats.etats.perimee_fait');
  },
  get aide_absente() {
    return i18n.t('admin:predicats.etats.aide_absente');
  },
  get condition_absente() {
    return i18n.t('admin:predicats.etats.condition_absente');
  },
  get hors_mandat() {
    return i18n.t('admin:predicats.etats.hors_mandat');
  },
  get invalide() {
    return i18n.t('admin:predicats.etats.invalide');
  },
};

/** Les états qui demandent une action : ils remontent en tête d'inventaire. */
const ORDRE_ETAT: Record<EtatPredicat, number> = {
  perimee_texte: 0,
  perimee_fait: 0,
  invalide: 1,
  aide_absente: 2,
  condition_absente: 2,
  hors_mandat: 2,
  a_revoir: 3,
  active: 4,
};

/**
 * Forme normale d'un prédicat simple. Miroir de `canoniser_predicat` : valeurs
 * triées et dédoublonnées, une seule valeur ramenée à `eq` / `neq`, plusieurs
 * promues en `in` / `not_in`. `none_in` garde sa liste, même à une valeur.
 *
 * Ce n'est pas cosmétique : sans elle, recomposer le prédicat d'origine depuis
 * le menu produirait une surcharge qui ne change rien, et figerait le YAML.
 */
export function canoniser(
  operateur: OperateurPredicat,
  valeurs: string[],
): { operateur: OperateurPredicat; valeurs: string[] } {
  const triees = [...new Set(valeurs)].sort();
  if (operateur === 'none_in') return { operateur, valeurs: triees };
  if (triees.length === 1) {
    if (operateur === 'in') return { operateur: 'eq', valeurs: triees };
    if (operateur === 'not_in') return { operateur: 'neq', valeurs: triees };
    return { operateur, valeurs: triees };
  }
  if (operateur === 'eq') return { operateur: 'in', valeurs: triees };
  if (operateur === 'neq') return { operateur: 'not_in', valeurs: triees };
  return { operateur, valeurs: triees };
}

/**
 * Le brouillon diffère-t-il du prédicat servi ? `null` quand il y revient — la
 * page appelle alors DELETE plutôt que PUT, comme pour les questions.
 */
export function predicatUtile(
  servi: { operateur: OperateurPredicat | ''; valeurs: string[] },
  brouillon: { operateur: OperateurPredicat; valeurs: string[] },
): { operateur: OperateurPredicat; valeurs: string[] } | null {
  if (brouillon.valeurs.length === 0) return null;
  const neuf = canoniser(brouillon.operateur, brouillon.valeurs);
  if (!servi.operateur) return neuf;
  const actuel = canoniser(servi.operateur, servi.valeurs);
  const memes =
    actuel.operateur === neuf.operateur &&
    actuel.valeurs.length === neuf.valeurs.length &&
    actuel.valeurs.every((v, i) => v === neuf.valeurs[i]);
  return memes ? null : neuf;
}

/**
 * « le statut du porteur **est parmi** association, commune ».
 *
 * La question du fait fait le sujet, les libellés des réponses l'objet : un
 * administrateur ne lit pas `{"in": ["association"]}`, il lit une phrase.
 */
export function phraseLisible(
  question: string | null,
  operateur: OperateurPredicat | '',
  valeurs: string[],
  reponses: { id: string; label: string }[],
  choixMultiple = false,
): string {
  if (!operateur || valeurs.length === 0) return '—';
  const parId = new Map(reponses.map((r) => [r.id, r.label]));
  const libelles = valeurs.map((v) => parId.get(v) ?? v).join(', ');
  const verbe =
    operateursPour(choixMultiple).find((o) => o.valeur === operateur)?.phrase ?? operateur;
  return i18n.t('admin:predicats.phrase', {
    sujet: question ?? i18n.t('admin:predicats.sujetParDefaut'),
    verbe,
    valeurs: libelles,
  });
}

export function filtrerConditions(
  conditions: AdminCondition[],
  recherche: string,
): AdminCondition[] {
  const q = normaliser(recherche);
  if (!q) return conditions;
  return conditions.filter((c) =>
    [c.aideSlug, c.aideNom, c.conditionId, c.text, c.factKey, c.question ?? ''].some((champ) =>
      normaliser(champ).includes(q),
    ),
  );
}

/**
 * L'inventaire des surcharges : ce qui demande une action D'ABORD (périmé,
 * invalide, orphelin), puis « à revoir », puis ce qui va bien.
 */
export function inventaireSurcharges(
  conditions: AdminCondition[],
  orphelines: ConditionOrpheline[],
): (AdminCondition | ConditionOrpheline)[] {
  const avec = [...conditions.filter((c) => c.surcharge), ...orphelines];
  return avec.sort((a, b) => {
    const ordre =
      ORDRE_ETAT[a.surcharge?.etat ?? 'active'] - ORDRE_ETAT[b.surcharge?.etat ?? 'active'];
    if (ordre !== 0) return ordre;
    return `${a.aideSlug}/${a.conditionId}`.localeCompare(`${b.aideSlug}/${b.conditionId}`);
  });
}

/** Une surcharge est-elle en attente d'arbitrage humain ? */
export function demandeUnArbitrage(etat: EtatPredicat | undefined): boolean {
  return etat !== undefined && etat !== 'active';
}

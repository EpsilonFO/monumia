import i18n from '@/i18n';
import { canDeleteDocument } from '@/lib/project-permissions';
import { canEditVisibility } from '@/lib/document-visibility';
import type { Document, ProjectRole } from '@/types';

/** Ce que fait une action : sert au composant à choisir son pictogramme. */
export type CleActionDocument =
  | 'renommer' | 'deplacer' | 'rattacher' | 'acces' | 'corbeille' | 'retirer'
  | 'restaurer' | 'supprimer';

/** Une action du menu ⋮ d'un document. */
export interface ActionDocument {
  label: string;
  onClick: () => void;
  destructive?: boolean;
  cle?: CleActionDocument;
}

/** Là où la liste s'affiche : on en RETIRE ce qui n'est pas à soi, on ne le jette pas. */
export interface IciDocument {
  type: 'monument' | 'projet';
  id: string;
  nom: string;
}

export interface GestesDocument {
  modifier: (d: Document) => void;
  /** « Changer de dossier » : changer son type, rien d'autre. */
  deplacer: (d: Document) => void;
  rattacher: (d: Document) => void;
  gererAcces: (d: Document) => void;
  corbeille: (d: Document) => void;
  retirer: (d: Document, ici: IciDocument) => void;
}

export interface ContexteDocument {
  userId?: string;
  role: ProjectRole | null;
  ici: IciDocument | null;
}

export interface DroitsDocument {
  /** Renommer, changer de dossier (type), modifier la note. */
  modifier: boolean;
  /** Régler qui le voit. */
  acces: boolean;
  /** Le geste destructif offert : jeter (l'auteur), retirer d'ici (un chef
   *  de projet non auteur), ou rien. */
  retrait: 'corbeille' | 'retirer' | null;
}

/**
 * Les droits sur un document, miroirs du serveur. Fonction pure.
 *
 * `role` est le rôle de l'utilisateur sur ce qui porte le document (monument
 * ou projet, le meilleur des deux) : un owner / co_owner a la main sur les
 * pièces des autres, un simple membre sur les siennes seulement
 * (`canDeleteDocument`, `canEditVisibility`).
 *
 * Jeter reste le geste de l'auteur : la corbeille est la sienne. Un chef de
 * projet qui n'en est pas l'auteur retire la pièce de l'endroit affiché, et
 * elle ne part en corbeille que si c'était sa dernière attache (serveur).
 */
export function droitsDocument(d: Document, ctx: ContexteDocument): DroitsDocument {
  const auteur = !!ctx.userId && d.userId === ctx.userId;
  const modifier = canDeleteDocument(auteur, ctx.role);
  // Un document sans monument ni projet est visible de son seul auteur : il
  // n'y a pas d'accès à régler.
  const acces = canEditVisibility(auteur, ctx.role) && (d.monumentIds.length > 0 || d.projetIds.length > 0);
  const { ici } = ctx;
  const estIci = !!ici && (ici.type === 'monument' ? d.monumentIds : d.projetIds).includes(ici.id);
  const retrait = auteur ? 'corbeille' : modifier && estIci ? 'retirer' : null;
  return { modifier, acces, retrait };
}

/**
 * Le menu ⋮ d'un document, le même sur Mes documents et dans les onglets
 * Documents d'un monument et d'un projet. Fonction pure. « Aperçu » et
 * « Télécharger », ouverts à qui voit le document, sont posés par le composant.
 */
export function actionsDocument(d: Document, ctx: ContexteDocument, gestes: GestesDocument): ActionDocument[] {
  const droits = droitsDocument(d, ctx);
  const actions: ActionDocument[] = [];
  if (droits.modifier) {
    actions.push({ cle: 'renommer', label: i18n.t('core:actionsDocument.renommer'), onClick: () => gestes.modifier(d) });
    actions.push({ cle: 'deplacer', label: i18n.t('core:actionsDocument.changerDeDossier'), onClick: () => gestes.deplacer(d) });
  }
  actions.push({ cle: 'rattacher', label: i18n.t('core:actionsDocument.rattacher'), onClick: () => gestes.rattacher(d) });
  if (droits.acces) actions.push({ cle: 'acces', label: i18n.t('core:actionsDocument.gererAcces'), onClick: () => gestes.gererAcces(d) });
  const { ici } = ctx;
  if (droits.retrait === 'corbeille') {
    actions.push({ cle: 'corbeille', label: i18n.t('core:actionsDocument.mettreALaCorbeille'), onClick: () => gestes.corbeille(d), destructive: true });
  } else if (droits.retrait === 'retirer' && ici) {
    actions.push({ cle: 'retirer', label: i18n.t('core:actionsDocument.retirerDe', { nom: ici.nom }), onClick: () => gestes.retirer(d, ici), destructive: true });
  }
  return actions;
}

/**
 * Une sélection de plusieurs documents, triée par ce qu'on peut en faire : la
 * barre de sélection n'applique à chacun que le geste que son menu offrirait.
 * `roleDe` : le rôle sur CE document (Mes documents mêle plusieurs monuments).
 */
export function repartirSelection(
  docs: Document[],
  ctx: { userId?: string; roleDe: (d: Document) => ProjectRole | null; ici: IciDocument | null },
): { modifiables: Document[]; aJeter: Document[]; aRetirer: Document[]; sansRetrait: Document[] } {
  const r = { modifiables: [] as Document[], aJeter: [] as Document[], aRetirer: [] as Document[], sansRetrait: [] as Document[] };
  docs.forEach((d) => {
    const droits = droitsDocument(d, { userId: ctx.userId, role: ctx.roleDe(d), ici: ctx.ici });
    if (droits.modifier) r.modifiables.push(d);
    if (droits.retrait === 'corbeille') r.aJeter.push(d);
    else if (droits.retrait === 'retirer') r.aRetirer.push(d);
    else r.sansRetrait.push(d);
  });
  return r;
}

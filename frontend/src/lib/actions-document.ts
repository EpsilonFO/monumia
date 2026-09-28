import { canDeleteDocument } from '@/lib/project-permissions';
import { canEditVisibility } from '@/lib/document-visibility';
import type { Document, ProjectRole } from '@/types';

/** Une action du menu ⋮ d'une ligne de document. */
export interface ActionDocument {
  label: string;
  onClick: () => void;
  destructive?: boolean;
}

/** Là où la liste s'affiche : on en RETIRE ce qui n'est pas à soi, on ne le jette pas. */
export interface IciDocument {
  type: 'monument' | 'projet';
  id: string;
  nom: string;
}

export interface GestesDocument {
  modifier: (d: Document) => void;
  rattacher: (d: Document) => void;
  gererAcces: (d: Document) => void;
  corbeille: (d: Document) => void;
  retirer: (d: Document, ici: IciDocument) => void;
}

/**
 * Le menu ⋮ d'un document, le même sur Mes documents et dans les onglets
 * Documents d'un monument et d'un projet. Fonction pure.
 *
 * `role` est le rôle de l'utilisateur sur ce qui porte le document (monument
 * ou projet, le meilleur des deux) : un owner / co_owner a la main sur les
 * pièces des autres, un simple membre sur les siennes seulement
 * (`canDeleteDocument`, `canEditVisibility`, miroirs du serveur).
 *
 * Jeter reste le geste de l'auteur : la corbeille est la sienne. Un chef de
 * projet qui n'en est pas l'auteur retire la pièce de l'endroit affiché, et
 * elle ne part en corbeille que si c'était sa dernière attache (serveur).
 */
export function actionsDocument(
  d: Document,
  ctx: { userId?: string; role: ProjectRole | null; ici: IciDocument | null },
  gestes: GestesDocument,
): ActionDocument[] {
  const auteur = !!ctx.userId && d.userId === ctx.userId;
  const peutModifier = canDeleteDocument(auteur, ctx.role);
  const actions: ActionDocument[] = [];
  if (peutModifier) actions.push({ label: 'Renommer ou changer le type', onClick: () => gestes.modifier(d) });
  actions.push({ label: 'Rattacher à un autre monument', onClick: () => gestes.rattacher(d) });
  // Un document sans monument ni projet est visible de son seul auteur : il
  // n'y a pas d'accès à régler.
  if (canEditVisibility(auteur, ctx.role) && (d.monumentIds.length > 0 || d.projetIds.length > 0)) {
    actions.push({ label: "Gérer l'accès", onClick: () => gestes.gererAcces(d) });
  }
  const { ici } = ctx;
  const estIci = !!ici && (ici.type === 'monument' ? d.monumentIds : d.projetIds).includes(ici.id);
  if (auteur) {
    actions.push({ label: 'Mettre à la corbeille', onClick: () => gestes.corbeille(d), destructive: true });
  } else if (peutModifier && ici && estIci) {
    actions.push({ label: `Retirer de ${ici.nom}`, onClick: () => gestes.retirer(d, ici), destructive: true });
  }
  return actions;
}

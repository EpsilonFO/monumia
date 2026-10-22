import { localeIntl } from '@/i18n/format';
import type { Document, PieceDemandee, ProjectDigest } from '@/types';

/**
 * « À déposer pour vos aides » : les pièces que demandent les aides des projets
 * d'un monument, et celles qui sont déjà là.
 *
 * Le serveur donne, par projet, les pièces citées par ses aides à portée
 * (`ProjectDigest.piecesDemandees`, cf. backend/services/pieces_demandees.py).
 * Ici on fait l'union sur plusieurs projets, où la même aide peut revenir, et on
 * croise avec les documents visibles.
 */
export interface PieceADeposer extends Omit<PieceDemandee, 'aideIds'> {
  aideIds: string[];
  /** Nombre d'aides DISTINCTES des projets retenus qui demandent la pièce. */
  nbAides: number;
  /** Les documents qui l'incarnent déjà (vide si la pièce reste à déposer). */
  documentIds: string[];
  deposee: boolean;
}

export interface PerimetrePieces {
  /** Les digests, indexés par projet (store des aides). */
  digests: Record<string, ProjectDigest | undefined>;
  /** Les projets dont les aides comptent (les projets ouverts, en général). */
  projetIds: string[];
  /** Le monument du périmètre, et TOUS ses projets (clos compris) : un document
   *  qui pend à l'un d'eux compte comme déposé. */
  monumentId: string;
  projetsDuMonument: string[];
  /** Les documents visibles (hors corbeille). */
  documents: Document[];
  /** L'utilisateur courant : une pièce `porteur` qu'il a déposée ailleurs
   *  (son RIB, ses statuts) reste la sienne partout. */
  userId?: string;
}

/** Vrai si le document pend au monument ou à l'un de ses projets. */
export function documentDuMonument(d: Document, monumentId: string, projetsDuMonument: string[]): boolean {
  return d.monumentIds.includes(monumentId) || d.projetIds.some((p) => projetsDuMonument.includes(p));
}

/**
 * Une pièce est déposée si un document visible du monument ou de ses projets
 * porte son `pieceId`. Pour une pièce `porteur`, un document que l'utilisateur
 * a déposé n'importe où compte aussi : c'est la règle de reprise des dossiers
 * (services/piece_reuse.py, `_candidat`), qui le joindra de toute façon.
 */
export function piecesADeposer(p: PerimetrePieces): PieceADeposer[] {
  const parPiece = new Map<string, { piece: PieceDemandee; aides: Set<string> }>();
  for (const pid of p.projetIds) {
    for (const piece of p.digests[pid]?.piecesDemandees ?? []) {
      const entree = parPiece.get(piece.pieceId) ?? { piece, aides: new Set<string>() };
      piece.aideIds.forEach((a) => entree.aides.add(a));
      parPiece.set(piece.pieceId, entree);
    }
  }

  const vivants = p.documents.filter((d) => !d.trashedAt && d.pieceId);
  const liste: PieceADeposer[] = [...parPiece.values()].map(({ piece, aides }) => {
    const documentIds = vivants
      .filter((d) => d.pieceId === piece.pieceId)
      .filter(
        (d) =>
          documentDuMonument(d, p.monumentId, p.projetsDuMonument) ||
          (piece.portee === 'porteur' && !!p.userId && d.userId === p.userId),
      )
      .map((d) => d.id);
    const aideIds = [...aides].sort();
    return { ...piece, aideIds, nbAides: aideIds.length, documentIds, deposee: documentIds.length > 0 };
  });

  // À déposer d'abord, les plus demandées en tête ; les déposées en fin de liste.
  return liste.sort(
    (a, b) =>
      Number(a.deposee) - Number(b.deposee) ||
      b.nbAides - a.nbAides ||
      a.nom.localeCompare(b.nom, localeIntl()),
  );
}

/** pieceId → nombre d'aides, pour la pastille « Sert à N aides » d'un document. */
export function nbAidesParPiece(pieces: PieceADeposer[]): Record<string, number> {
  return Object.fromEntries(pieces.map((x) => [x.pieceId, x.nbAides]));
}

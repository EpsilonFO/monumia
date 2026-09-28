import { useMemo } from 'react';
import { useAideStore } from '@/stores/useAideStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { piecesADeposer, type PieceADeposer } from '@/lib/pieces-a-deposer';
import type { Document, Projet } from '@/types';

/**
 * Les pièces que demandent les aides des projets d'un monument, calculées sur
 * les digests du dashboard et les documents visibles.
 *
 * `projetIds` restreint le calcul à ces projets (l'onglet Documents d'un
 * projet) ; sans lui, ce sont les projets OUVERTS du monument qui comptent.
 *
 * `documentsEnPlus` : une liste chargée à part (l'onglet d'un monument ou d'un
 * projet lit sa propre liste), unie à celle du store par id.
 */
export function usePiecesADeposer(
  monumentId: string | null,
  projetIds?: string[],
  documentsEnPlus?: Document[],
): { pieces: PieceADeposer[]; projets: Projet[] } {
  const digests = useAideStore((s) => s.digestsByProjet);
  const tousLesProjets = useProjetStore((s) => s.projets);
  const duStore = useDocumentStore((s) => s.documents);
  const documents = useMemo(() => {
    if (!documentsEnPlus?.length) return duStore;
    const connus = new Set(duStore.map((d) => d.id));
    return [...duStore, ...documentsEnPlus.filter((d) => !connus.has(d.id))];
  }, [duStore, documentsEnPlus]);
  const userId = useAuthStore((s) => s.user?.id);
  const cle = projetIds?.join(',');

  return useMemo(() => {
    if (!monumentId) return { pieces: [], projets: [] };
    const duMonument = tousLesProjets.filter((p) => p.monumentId === monumentId);
    const retenus = cle !== undefined
      ? duMonument.filter((p) => cle.split(',').includes(p.id))
      : duMonument.filter((p) => !p.clotureAt);
    const pieces = piecesADeposer({
      digests,
      projetIds: retenus.map((p) => p.id),
      monumentId,
      projetsDuMonument: duMonument.map((p) => p.id),
      documents,
      userId,
    });
    return { pieces, projets: retenus };
  }, [monumentId, cle, digests, tousLesProjets, documents, userId]);
}

import type { Document } from '@/types';

export interface GroupedDocuments {
  /** monumentId → documents rattachés (un doc multi-projets apparaît sous chacun). */
  byProject: Map<string, Document[]>;
  /** Documents sans aucun projet (imports directs « personnels »). */
  sansProjet: Document[];
}

/** Regroupe des documents (déjà non-corbeille) par projet, + une pile « sans projet ». */
export function groupDocumentsByProject(docs: Document[]): GroupedDocuments {
  const byProject = new Map<string, Document[]>();
  const sansProjet: Document[] = [];

  for (const doc of docs) {
    if (doc.monumentIds.length === 0) {
      sansProjet.push(doc);
      continue;
    }
    for (const mid of doc.monumentIds) {
      const list = byProject.get(mid) ?? [];
      list.push(doc);
      byProject.set(mid, list);
    }
  }

  return { byProject, sansProjet };
}

import { useRef, useState, type DragEvent } from 'react';
import type { DocumentType } from '@/types';

/** Un fichier glissé depuis l'ordinateur (et non un texte ou un lien). */
const glisseDesFichiers = (e: DragEvent) => [...e.dataTransfer.types].includes('Files');

/** Le dossier (`data-dossier`) sous le pointeur, et s'il survole la grille des dossiers. */
function cibleDe(e: DragEvent): { dossier: DocumentType | null; grille: boolean } {
  const el = e.target instanceof Element ? e.target : null;
  const dossier = (el?.closest('[data-dossier]') as HTMLElement | null)?.dataset.dossier as DocumentType | undefined;
  return { dossier: dossier ?? null, grille: !!el?.closest('[data-dossiers]') };
}

/**
 * Glisser des fichiers n'importe où sur l'espace : un voile bleu dit où ils
 * iront, et le lâcher ouvre la fenêtre d'ajout. Lâchés sur un dossier, ils s'y
 * rangent : le voile s'efface au-dessus de la grille des dossiers pour qu'on
 * voie celui qu'on vise. Le compteur de profondeur évite le clignotement quand
 * le pointeur passe d'un enfant à l'autre.
 */
export function useDepotGlisse(onDeposer: ((fichiers: File[], dossier: DocumentType | null) => void) | null) {
  const profondeur = useRef(0);
  const [actif, setActif] = useState(false);
  const [cible, setCible] = useState<{ dossier: DocumentType | null; grille: boolean }>({ dossier: null, grille: false });
  const fin = () => {
    profondeur.current = 0;
    setActif(false);
    setCible({ dossier: null, grille: false });
  };
  if (!onDeposer) return { actif: false, survole: null, surDossiers: false, gestionnaires: {} };
  return {
    actif,
    survole: actif ? cible.dossier : null,
    surDossiers: actif && cible.grille,
    gestionnaires: {
      onDragEnter: (e: DragEvent) => {
        if (!glisseDesFichiers(e)) return;
        e.preventDefault();
        profondeur.current += 1;
        setActif(true);
      },
      onDragOver: (e: DragEvent) => {
        if (!glisseDesFichiers(e)) return;
        e.preventDefault();
        const c = cibleDe(e);
        setCible((p) => (p.dossier === c.dossier && p.grille === c.grille ? p : c));
      },
      onDragLeave: () => {
        profondeur.current = Math.max(0, profondeur.current - 1);
        if (profondeur.current === 0) fin();
      },
      onDrop: (e: DragEvent) => {
        if (!glisseDesFichiers(e)) return;
        e.preventDefault();
        const { dossier } = cibleDe(e);
        fin();
        const fichiers = [...e.dataTransfer.files];
        if (fichiers.length) onDeposer(fichiers, dossier);
      },
    },
  };
}

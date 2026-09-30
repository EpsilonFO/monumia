import type { ReactNode } from 'react';

/**
 * Les pictogrammes de la maquette `monumia-documents.html` que
 * `shared/ecrans/Picto` n'a pas, tracé pour tracé. Gardés ici plutôt que dans
 * le fichier partagé : ils ne servent qu'à l'espace documents.
 */
const TRACES = {
  tous: [1.9, <><path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10.5a.5.5 0 0 1-.5-.5V4a.5.5 0 0 1 .5-.5z" /><path d="M14 3.5V8h4" /></>],
  recents: [1.9, <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>],
  corbeille: [1.9, <path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13" />],
  pieces: [1.9, <><path d="M9 6h11M9 12h11M9 18h11" /><path d="m3.5 6 1.2 1.2L7 5M3.5 12l1.2 1.2L7 11M3.5 18l1.2 1.2L7 17" /></>],
  oeil: [1.9, <><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="3" /></>],
  deplacer: [1.9, <><path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.4h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" /><path d="M10 13h6M13.5 10.5 16 13l-2.5 2.5" /></>],
  rattacher: [1.9, <><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></>],
  trier: [2, <path d="M8 5v14M4 15l4 4 4-4M16 19V5M12 9l4-4 4 4" />],
  lignes: [2, <path d="M4 6h16M4 12h16M4 18h16" />],
  grille: [1.9, <><rect x="4" y="4" width="6.5" height="6.5" rx="1.5" /><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5" /><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5" /><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5" /></>],
  suivant: [2, <path d="m9 6 6 6-6 6" />],
  restaurer: [1.9, <><path d="M4 12a8 8 0 1 0 2.3-5.7" /><path d="M4 4v5h5" /></>],
} satisfies Record<string, [number, ReactNode]>;

export type NomPictoDoc = keyof typeof TRACES;

export function PictoDoc({ nom, className = 'i' }: { nom: NomPictoDoc; className?: string }) {
  const [trait, trace] = TRACES[nom];
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={trait}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {trace}
    </svg>
  );
}

/** Le dossier plein des cartes de dossier : un remplissage, pas un trait. */
export function PictoDossierPlein({ className = 'fi' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M3 6.5A2.5 2.5 0 0 1 5.5 4h4.2l2.1 2.4h6.7A2.5 2.5 0 0 1 21 8.9V17.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z" />
    </svg>
  );
}

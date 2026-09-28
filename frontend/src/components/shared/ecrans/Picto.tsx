import type { ReactNode } from 'react';
import { IconDocuments } from '@/components/icons';

/**
 * Les pictogrammes des maquettes d'écran, tracé pour tracé et chacun avec son
 * épaisseur de trait : c'est ce qui les distingue de `components/icons` et de
 * l'`Ico` de la fiche d'aide (trait unique à 1,7).
 */
const PICTOS = {
  fleche: [2.1, <path d="M5 12h14M13 6l6 6-6 6" />],
  retour: [2.1, <path d="M19 12H5M11 6l-6 6 6 6" />],
  coche: [2.8, <path d="m5 12.5 4.5 4.5L19 7.5" />],
  chevron: [2, <path d="m6 9 6 6 6-6" />],
  plus: [2.2, <path d="M12 5v14M5 12h14" />],
  croix: [2.2, <path d="M7 7l10 10M17 7 7 17" />],
  question: [
    2.3,
    <>
      <path d="M9.2 9.2a2.9 2.9 0 1 1 4 2.7c-.8.4-1.2 1-1.2 1.8v.5" />
      <path d="M12 17.6h.01" />
    </>,
  ],
  cloche: [
    1.9,
    <>
      <path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15z" />
      <path d="M10 20.5a2 2 0 0 0 4 0" />
    </>,
  ],
  livre: [
    1.8,
    <>
      <path d="M3.5 5.5c3-1 5.5-.8 8.5 1 3-1.8 5.5-2 8.5-1v13c-3-1-5.5-.8-8.5 1-3-1.8-5.5-2-8.5-1z" />
      <path d="M12 6.5v13" />
    </>,
  ],
  photo: [
    1.9,
    <>
      <path d="M4 8h3l2-2.5h6L17 8h3v11H4z" />
      <circle cx="12" cy="13" r="3.5" />
    </>,
  ],
  eglise: [
    1.8,
    <path d="M12 2v4M10 4h4M7 21V11l5-5 5 5v10M3 21v-6l4-3M21 21v-6l-4-3M10 21v-4a2 2 0 0 1 4 0v4M2 21h20" />,
  ],
  doc: [
    1.9,
    <>
      <path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10.5a.5.5 0 0 1-.5-.5V4a.5.5 0 0 1 .5-.5z" />
      <path d="M14 3.5V8h4M9 12h6M9 16h6" />
    </>,
  ],
  telecharger: [2, <path d="M12 4v12M7 11l5 5 5-5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />],
  envoyer: [2, <path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />],
  euro: [
    1.9,
    <>
      <path d="M17.5 6.5A6.5 6.5 0 0 0 7 12a6.5 6.5 0 0 0 10.5 5.5" />
      <path d="M4.5 10h9M4.5 14h9" />
    </>,
  ],
  dossier: [1.9, <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />],
  grille: [
    1.8,
    <>
      <rect x="4" y="4" width="6.5" height="6.5" rx="1.5" />
      <rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5" />
      <rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5" />
      <rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5" />
    </>,
  ],
  main: [
    1.8,
    <>
      <path d="M3 15h3l4 2h4a1.5 1.5 0 0 0 0-3h-3M6 15v5M14 17l5.3-2.4a1.6 1.6 0 0 1 1.5 2.8L14 21H6" />
      <circle cx="15" cy="7" r="3" />
    </>,
  ],
  maison: [1.8, <path d="M4 20V10l8-6 8 6v10M9 20v-6h6v6" />],
  cadenas: [
    1.9,
    <>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
    </>,
  ],
  crayon: [
    1.9,
    <>
      <path d="M4 20h4L19 9l-4-4L4 16v4z" />
      <path d="m13.5 6.5 4 4" />
    </>,
  ],
  refaire: [
    1.9,
    <>
      <path d="M20 11a8 8 0 1 0-2.3 5.7" />
      <path d="M20 4v7h-7" />
    </>,
  ],
  loupe: [
    2,
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </>,
  ],
  equipe: [
    1.8,
    <>
      <circle cx="9" cy="9" r="3" />
      <path d="M3.5 19c.6-3 2.8-4.5 5.5-4.5s4.9 1.5 5.5 4.5" />
      <circle cx="17" cy="8" r="2.5" />
      <path d="M16 13.2c2.4 0 4 1.3 4.6 3.8" />
    </>,
  ],
} satisfies Record<string, [number, ReactNode]>;

export type NomPicto = keyof typeof PICTOS;

export function Picto({ nom, className = 'i' }: { nom: NomPicto; className?: string }) {
  // Les documents gardent l'icône de toujours (décision du 2026-09-28) : barre
  // haute, onglets, partout où l'app parle de documents.
  if (nom === 'doc') return <IconDocuments className={className} aria-hidden="true" />;
  const [trait, trace] = PICTOS[nom];
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

/** Les trois points verticaux (« plus d'actions ») : un remplissage, pas un trait. */
export function PictoPoints({ className = 'i' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <circle cx="12" cy="5.5" r="1.7" />
      <circle cx="12" cy="12" r="1.7" />
      <circle cx="12" cy="18.5" r="1.7" />
    </svg>
  );
}

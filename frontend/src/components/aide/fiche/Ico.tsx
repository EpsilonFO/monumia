import type { ReactNode } from 'react';

/**
 * Les pictogrammes de la maquette, tracé pour tracé. Ils ne viennent pas de
 * `components/icons` : même trait (1,7), même grille de 24, et c'est ce qui fait
 * que la fiche se lit comme le dessin du designer.
 */
const TRACES = {
  financeur: <path d="M3.5 9 12 4.5 20.5 9M5 9v8m4.7-8v8m4.6-8v8M19 9v8M3.5 19.5h17" />,
  maison: <path d="M4 20V10l8-5.5L20 10v10M9 20v-5.5h6V20M2.5 20h19" />,
  document: (
    <>
      <path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10A.5.5 0 0 1 7 20V3.5Z" />
      <path d="M14 3.5V8h4M10 12h5M10 15.5h5" />
    </>
  ),
  calendrier: (
    <>
      <rect x="4" y="5.5" width="16" height="14.5" rx="2" />
      <path d="M4 10h16M8.5 3.5v3.5m7-3.5v3.5" />
    </>
  ),
  depot: (
    <>
      <rect x="3" y="4.5" width="18" height="12.5" rx="2" />
      <path d="M8 20h8M12 17v3M12 13.5V8m-2.5 2.5L12 8l2.5 2.5" />
    </>
  ),
  cumul: (
    <>
      <rect x="3.5" y="8" width="11" height="11" rx="2" />
      <path d="M9.5 8V6a1.5 1.5 0 0 1 1.5-1.5h8A1.5 1.5 0 0 1 20.5 6v8a1.5 1.5 0 0 1-1.5 1.5h-4.5" />
    </>
  ),
  contact: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.5 6.5 8.5 6 8.5-6" />
    </>
  ),
  externe: (
    <path d="M13.5 4.5H19.5V10.5M19.5 4.5l-8 8M17 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 4 18.5v-10A1.5 1.5 0 0 1 5.5 7H10" />
  ),
  coche: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  montant: <path d="M17 6.5A6.5 6.5 0 1 0 17 17.5M4 10.5h9M4 13.5h9" />,
  croix: <path d="M7 7l10 10M17 7 7 17" />,
  ampoule: (
    <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.2h5c0-.9.4-1.7 1.1-2.2A6 6 0 0 0 12 3Z" />
  ),
  fleche: <path d="M5 12h14m-5-5 5 5-5 5" />,
  livre: (
    <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5v-13ZM20 5.5A1.5 1.5 0 0 0 18.5 4H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5v-13Z" />
  ),
  loupe: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-4.2-4.2" />
    </>
  ),
  fichier: (
    <>
      <path d="M7 3.5h7l4 4V20.5H7z" />
      <path d="M14 3.5V8h4" />
    </>
  ),
  formulaire: (
    <>
      <path d="M6 3.5h8l4 4V20.5H6z" />
      <path d="m9 14 2 2 4-4" />
    </>
  ),
  delai: (
    <>
      <circle cx="12" cy="12.5" r="7.5" />
      <path d="M12 8.5v4l2.5 2M9.5 2.5h5" />
    </>
  ),
  cloche: <path d="M12 4a5.5 5.5 0 0 0-5.5 5.5v3.2L5 15.5h14l-1.5-2.8V9.5A5.5 5.5 0 0 0 12 4Zm-2 13.5a2 2 0 0 0 4 0" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  info: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5.5M12 7.8v.2" />
    </>
  ),
} satisfies Record<string, ReactNode>;

export type NomIco = keyof typeof TRACES;

export function Ico({ nom }: { nom: NomIco }) {
  return (
    <svg
      className="i"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {TRACES[nom]}
    </svg>
  );
}

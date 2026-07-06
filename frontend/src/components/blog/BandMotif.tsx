import type { ReactNode } from 'react';

/**
 * Motifs décoratifs des bandeaux d'articles — vocabulaire du bâti :
 * arche, colonnade, appareillage de pierre, toiture. Le motif est choisi
 * de façon déterministe à partir du slug, pour varier d'une carte à l'autre
 * sans jamais changer au re-rendu.
 */

const MOTIFS = ['arche', 'colonnade', 'appareillage', 'toiture'] as const;
type Motif = (typeof MOTIFS)[number];

function pickMotif(slug: string): Motif {
  let h = 0;
  for (const ch of slug) h = (h + ch.charCodeAt(0)) % MOTIFS.length;
  return MOTIFS[h];
}

const PATHS: Record<Motif, ReactNode> = {
  // Deux arcs concentriques posés sur le sol, façon porche roman.
  arche: (
    <>
      <path d="M6 80 A52 52 0 0 1 110 80" />
      <path d="M24 80 A34 34 0 0 1 92 80" />
    </>
  ),
  // Entablement et trois fûts de colonnes.
  colonnade: (
    <>
      <path d="M8 14 H112" />
      <path d="M24 22 V80 M60 22 V80 M96 22 V80" />
      <path d="M16 22 H32 M52 22 H68 M88 22 H104" />
    </>
  ),
  // Assises de pierre à joints décalés.
  appareillage: (
    <>
      <path d="M0 26 H120 M0 50 H120 M0 74 H120" />
      <path d="M40 26 V50 M84 26 V50" />
      <path d="M20 50 V74 M62 50 V74 M104 50 V74" />
    </>
  ),
  // Double pente de toiture, charpente apparente.
  toiture: (
    <>
      <path d="M8 64 L60 16 L112 64" />
      <path d="M30 64 L60 36 L90 64" />
      <path d="M60 16 V64" />
    </>
  ),
};

export function BandMotif({ slug, className }: { slug: string; className?: string }) {
  const motif = pickMotif(slug);
  return (
    <svg
      viewBox="0 0 120 80"
      aria-hidden
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
    >
      {PATHS[motif]}
    </svg>
  );
}

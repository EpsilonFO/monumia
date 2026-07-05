import type { IconProps } from './types';
import { CLOCHE_D, ECROU_D, TELECHARGEMENT_D } from './founder-paths';

/**
 * Icônes propres à Monumia — celles qu'aucune bibliothèque ne peut fournir.
 *
 * - `IconMonument` : le médaillon — le quadrilobe aux proportions EXACTES du
 *   logo (Clover : lobes r 23 centrés à 21, mis à l'échelle ×2,54), assez
 *   grand pour rester lisible partout (Ø 87 % du cadre), encadrant un donjon
 *   crénelé — comme les médaillons quadrilobés qui encadrent les reliefs des
 *   façades gothiques. Le monument DANS la marque.
 * - `IconProjet` : un monument sous échafaudage (le projet = un chantier).
 * - `IconClocheMonumia` / `IconEcrouMonumia` / `IconTelechargementMonumia` :
 *   les tracés fait-main du fondateur (remplis, ronds, ligne en écho).
 *   Riches : à réserver aux grands formats (≥ 22 px — tuiles, zones de dépôt,
 *   états vides), jamais en métadonnée de 14 px.
 */

/* ---------------------------------------------------------------- monument */

// Médaillon : quadrilobe plein cadre aux proportions du logo (union de 4
// cercles r 58.5 centrés à 53.5 du cœur, contour en 8 arcs), lavis + trait ;
// à l'intérieur, un donjon plein à trois merlons, porte percée en blanc.
const MEDAILLON =
  'M 128 16 A 58.5 58.5 0 0 1 186.3 69.7 A 58.5 58.5 0 0 1 240 128 ' +
  'A 58.5 58.5 0 0 1 186.3 186.3 A 58.5 58.5 0 0 1 128 240 A 58.5 58.5 0 0 1 69.7 186.3 ' +
  'A 58.5 58.5 0 0 1 16 128 A 58.5 58.5 0 0 1 69.7 69.7 A 58.5 58.5 0 0 1 128 16 Z';
const DONJON =
  'M 96 188 L 96 64 L 112 64 L 112 86 L 120 86 L 120 64 L 136 64 L 136 86 ' +
  'L 144 86 L 144 64 L 160 64 L 160 188 Z';
const PORTE = 'M 118 188 L 118 162 A 10 10 0 0 1 138 162 L 138 188 Z';

// Calibré sur Phosphor (trait ≈ 16/256 en regular) pour la parité optique en nav.
const STROKE_BY_WEIGHT: Record<string, number> = {
  thin: 8,
  light: 12,
  regular: 16,
  bold: 22,
  duotone: 16,
  fill: 16,
};

// `strokeWidth` est ignoré (comme sur les icônes Phosphor, pleines) : les valeurs
// héritées de l'ère lucide (1.5–2) seraient invisibles dans un viewBox de 256.
export function IconMonument({ size = 20, weight = 'duotone', strokeWidth: _sw, ...props }: IconProps) {
  if (weight === 'fill') {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        viewBox="0 0 256 256"
        fill="currentColor"
        aria-hidden
        {...props}
      >
        <path fillRule="evenodd" d={`${MEDAILLON} ${DONJON}`} />
      </svg>
    );
  }
  const sw = STROKE_BY_WEIGHT[weight] ?? 16;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 256 256"
      fill="currentColor"
      aria-hidden
      {...props}
    >
      {weight === 'duotone' && <path d={MEDAILLON} opacity={0.2} />}
      <path fillRule="evenodd" d={`${DONJON} ${PORTE}`} />
      <g fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
        <path d={MEDAILLON} />
      </g>
    </svg>
  );
}

/* ------------------------------------------------------------------ projet */

// Un projet = un monument en chantier de restauration : la même famille de
// silhouette, décalée à droite, sous ÉCHAFAUDAGE (montant + 3 traverses).
// L'oculus rond remplace la rosace — le quadrilobe reste réservé au monument.
const PROJET = {
  facade: 'M 150 42 L 218 102 L 218 214 L 82 214 L 82 102 Z',
  porte: 'M 128 214 L 128 176 A 22 22 0 0 1 172 176 L 172 214',
  montant: 'M 38 62 L 38 214',
  traverses: ['M 38 92 L 82 92', 'M 38 138 L 82 138', 'M 38 184 L 82 184'],
};

export function IconProjet({ size = 20, weight = 'duotone', strokeWidth: _sw, ...props }: IconProps) {
  const sw = STROKE_BY_WEIGHT[weight] ?? 16;
  const solid = weight === 'fill';
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 256 256"
      fill="currentColor"
      aria-hidden
      {...props}
    >
      {(solid || weight === 'duotone') && (
        <path
          fillRule="evenodd"
          d={`${PROJET.facade} ${PROJET.porte} Z M 164 108 A 14 14 0 1 0 136 108 A 14 14 0 1 0 164 108 Z`}
          opacity={solid ? 1 : 0.2}
        />
      )}
      {!solid && <circle cx={150} cy={108} r={14} />}
      <g fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
        {!solid && <path d={PROJET.facade} />}
        {!solid && <path d={PROJET.porte} />}
        <path d={PROJET.montant} />
        {PROJET.traverses.map((t) => (
          <path key={t} d={t} />
        ))}
      </g>
    </svg>
  );
}

/* ----------------------------------------------- tracés fait-main (vedettes) */

function founderIcon(d: string) {
  function FounderIcon({ size = 20, weight: _weight, strokeWidth: _sw, ...props }: IconProps) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        viewBox="0 0 100 100"
        fill="currentColor"
        aria-hidden
        {...props}
      >
        <path d={d} fillRule="evenodd" clipRule="evenodd" />
      </svg>
    );
  }
  return FounderIcon;
}

export const IconClocheMonumia = founderIcon(CLOCHE_D);
export const IconEcrouMonumia = founderIcon(ECROU_D);
export const IconTelechargementMonumia = founderIcon(TELECHARGEMENT_D);

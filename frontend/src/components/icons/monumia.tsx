import type { CSSProperties } from 'react';
import type { IconProps } from './types';
import { CLOCHE_D, ECROU_D, TELECHARGEMENT_D } from './founder-paths';

/**
 * Icônes propres à Monumia — celles qu'aucune bibliothèque ne peut fournir.
 *
 * - `IconMonument` : une façade à pignon percée d'une ROSACE — le quadrilobe
 *   aux proportions EXACTES du logo (lobes r 58.5 décalés de 53.5, réduits
 *   ×0,32), en trait au-dessus d'une porte en plein cintre. La marque en
 *   détail (la rosace), pas en cadre : densité d'encre alignée sur Phosphor.
 * - `IconProjet` : un monument sous échafaudage (le projet = un chantier).
 * - `IconClocheMonumia` / `IconEcrouMonumia` / `IconTelechargementMonumia` :
 *   les tracés fait-main du fondateur (remplis, ronds, ligne en écho).
 *   Riches : à réserver aux grands formats (≥ 22 px — tuiles, zones de dépôt,
 *   états vides), jamais en métadonnée de 14 px.
 */

/* ---------------------------------------------------------------- monument */

// Façade à pignon (même famille qu'IconProjet), rosace quadrilobée en trait
// (8 arcs, proportions du logo réduites ×0,32 : r 18.8, lobes décalés de 18.7),
// porte en plein cintre. Lavis duotone = la façade seule. Emprise quasi pleine
// (40–216) à la manière des bâtiments Phosphor ; 14 u d'air entre rosace et
// porte, traits compris — elles ne doivent jamais se toucher.
const FACADE = 'M 128 30 L 216 100 L 216 220 L 40 220 L 40 100 Z';
const PORTE = 'M 106 220 L 106 190 A 22 22 0 0 1 150 190 L 150 220';
const ROSACE =
  'M 128 66 A 18.8 18.8 0 0 1 146.7 83.3 A 18.8 18.8 0 0 1 164 102 ' +
  'A 18.8 18.8 0 0 1 146.7 120.7 A 18.8 18.8 0 0 1 128 138 A 18.8 18.8 0 0 1 109.3 120.7 ' +
  'A 18.8 18.8 0 0 1 92 102 A 18.8 18.8 0 0 1 109.3 83.3 A 18.8 18.8 0 0 1 128 66 Z';

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
        <path fillRule="evenodd" d={`${FACADE} ${PORTE} Z ${ROSACE}`} />
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
      {weight === 'duotone' && <path d={FACADE} opacity={0.2} />}
      <g fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
        <path d={FACADE} />
        <path d={PORTE} />
        <path d={ROSACE} />
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

/* ------------------------------------------------------------------- logo */

/**
 * La fleur Monumia (`public/logo.svg`) servie en masque CSS, exactement comme
 * sur la landing : la couleur vient du token de thème et non d'un aplat cuit
 * dans un PNG. Un seul orange sur toute la plateforme, mode sombre compris.
 *
 * `label` rend le logo annonçable (marque cliquable) ; sans lui il est décoratif.
 */
const LOGO_URL = 'url(/logo.svg)';

export function LogoMonumia({ className = '', label, color = 'var(--accent)', style }: {
  className?: string;
  /** Texte alternatif. Omis = purement décoratif (le nom est écrit à côté). */
  label?: string;
  /** Couleur de la fleur. Par défaut l'orange de la charte. */
  color?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      className={className}
      {...(label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true })}
      style={{
        display: 'inline-block',
        backgroundColor: color,
        WebkitMaskImage: LOGO_URL,
        maskImage: LOGO_URL,
        WebkitMaskRepeat: 'no-repeat',
        maskRepeat: 'no-repeat',
        WebkitMaskPosition: 'center',
        maskPosition: 'center',
        WebkitMaskSize: 'contain',
        maskSize: 'contain',
        ...style,
      }}
    />
  );
}

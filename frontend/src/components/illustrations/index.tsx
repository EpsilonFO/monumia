import type { CSSProperties } from 'react';
import { C } from '@/lib/brand';
import { LogoMonumia } from '@/components/icons/monumia';

/**
 * La fleur Monumia en ornement décoratif : le VRAI logo (`public/logo.svg`,
 * servi en masque CSS comme sur la landing), et non un quadrilobe approché.
 *
 * La couleur vient de `currentColor` : les appelants continuent de la piloter
 * par `className="text-white"` ou `style={{ color: … }}`, opacité comprise.
 */
export function Clover({
  size = 88,
  className,
  style,
}: {
  size?: number;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <LogoMonumia
      className={className}
      color="currentColor"
      style={{ width: size, height: size, ...style }}
    />
  );
}

/** Scène rassurante « tout est à jour » : disque pâle + fleur fantôme + coche. */
export function AllClear({ className }: { className?: string }) {
  return (
    <span
      className={`relative flex h-16 w-16 items-center justify-center rounded-full ${className ?? ''}`}
      style={{ background: C.paleBlue }}
      aria-hidden
    >
      <Clover size={42} style={{ color: C.blue, opacity: 0.1, position: 'absolute' }} />
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke={C.orange} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 12.5 l4 4 l10 -11" />
      </svg>
    </span>
  );
}

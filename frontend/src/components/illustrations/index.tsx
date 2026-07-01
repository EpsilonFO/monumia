import type { CSSProperties } from 'react';
import { C } from '@/lib/brand';

/** Quadrilobe Monumia (4 cercles r23 centrés à 21 du centre) — emblème décoratif. */
export function Clover({
  size = 88,
  className,
  style,
}: {
  size?: number;
  className?: string;
  style?: CSSProperties;
}) {
  const c = 44;
  const d = 21;
  const r = 23;
  return (
    <svg viewBox="0 0 88 88" width={size} height={size} aria-hidden className={className} style={style}>
      <g fill="currentColor">
        <circle cx={c} cy={c - d} r={r} />
        <circle cx={c} cy={c + d} r={r} />
        <circle cx={c - d} cy={c} r={r} />
        <circle cx={c + d} cy={c} r={r} />
      </g>
    </svg>
  );
}

/** Scène rassurante « tout est à jour » : disque pâle + quadrilobe fantôme + coche. */
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

// Charte Monumia — valeurs reprises telles quelles de la landing (branche landing-page)
export const C = {
  blue:       '#0a369d', // bleu profond — institutionnel
  blueLight:  '#5c95ff', // bleu clair — liens, infographies
  blueDark:   '#072a72', // bleu foncé — frises, accents sidebar
  orange:     '#f17105', // orange — action, signature (CTA)
  orangeVif:  '#fc8905', // orange vif — accentuation, badges (parcimonie)
  cream:      '#fdf9f0', // crème — fond par excellence
  ink:        '#222b35', // noir bleuté — corps de texte
  card:       '#fffefb', // carte, à peine plus claire que le crème
  border:     '#ece3d2', // bordure chaude
  paleBlue:   '#eef3ff', // teinte du bleu clair
  paleOrange: '#feeedd', // teinte de l'orange
  danger:     '#c0271d', // rouge — échéance imminente (< 30 j) ou dépassée
  paleDanger: '#fbeae8', // teinte du rouge
  grayFg:     '#4a5160', // texte secondaire lisible sur crème (AA)
  grayMuted:  '#6a7180', // texte tertiaire / hint
} as const;

// Police titres (PT Serif) — pour les styles inline ; le corps utilise Inter via var(--font-sans)
export const SERIF = "'PT Serif', Georgia, 'Times New Roman', serif";

/**
 * Code couleur unique des échéances, appliqué partout sur le site.
 *   • moins de 30 jours (ou dépassée) → rouge
 *   • entre 30 et 100 jours           → orange
 *   • plus de 100 jours               → bleu
 * Les seuils sont définis dans `deadlineLabel` (lib/date-utils), qui produit ces
 * quatre clés d'urgence. `tint` = fond clair, `fg` = texte/accent, `node` = pastille.
 */
export type DeadlineUrgency = 'past' | 'urgent' | 'warning' | 'normal';

export const DEADLINE_TONE: Record<DeadlineUrgency, { fg: string; tint: string; node: string }> = {
  past:    { fg: C.danger, tint: C.paleDanger, node: C.danger }, // dépassée → rouge
  urgent:  { fg: C.danger, tint: C.paleDanger, node: C.danger }, // < 30 j   → rouge
  warning: { fg: C.orange, tint: C.paleOrange, node: C.orange }, // 30–100 j → orange
  normal:  { fg: C.blue,   tint: C.paleBlue,   node: C.blueLight }, // > 100 j → bleu
} as const;

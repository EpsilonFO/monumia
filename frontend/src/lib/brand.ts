// Charte Monumia — pointe vers les tokens de thème CSS (mode sombre automatique)
export const C = {
  blue:       'var(--primary)',        // bleu profond — institutionnel
  blueLight:  'var(--blue-light)',     // bleu clair — liens, infographies
  blueDark:   'var(--blue-dark)',      // bleu foncé — frises, accents sidebar
  orange:     'var(--accent)',         // orange — action, signature (CTA)
  orangeVif:  'var(--orange-vif)',     // orange vif — accentuation, badges
  cream:      'var(--background)',     // crème — fond par excellence
  ink:        'var(--foreground)',     // noir bleuté — corps de texte
  card:       'var(--card)',           // carte
  border:     'var(--border)',         // bordure
  paleBlue:   'var(--secondary)',      // teinte du bleu clair
  paleOrange: 'var(--warning-muted)', // teinte de l'orange
  danger:     'var(--destructive)',    // rouge — échéance imminente/dépassée
  paleDanger: 'var(--destructive-muted)', // teinte du rouge
  grayFg:     'var(--gray-fg)',        // texte secondaire lisible (AA)
  grayMuted:  'var(--gray-muted)',     // texte tertiaire / hint
  success:      'var(--success)',        // vert — article lu / réussite
  successMuted: 'var(--success-muted)',  // vert clair — fond « lu »
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

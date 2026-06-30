import {
  IconDevis, IconImage, IconArchive, IconParchemin, IconRegle, IconDiagnostic,
  IconModifier, IconDocument, IconDocumentValide, IconListe,
  type IconComponent,
} from '@/components/icons';
import type { DocumentType } from '@/types';

const ICONS: Record<string, IconComponent> = {
  photo: IconImage, plan: IconDevis, devis: IconListe, facture: IconDevis,
  attestation: IconDocumentValide, extrait_cadastral: IconDevis, cerfa: IconDocumentValide,
  arrete: IconRegle, diagnostic: IconDiagnostic, rapport: IconParchemin, correspondance: IconModifier, autre: IconArchive,
};

const LABELS: Record<string, string> = {
  photo: 'Photo', plan: 'Plan', devis: 'Devis', facture: 'Facture',
  attestation: 'Attestation', extrait_cadastral: 'Extrait cadastral', cerfa: 'CERFA',
  arrete: 'Arrêté', diagnostic: 'Diagnostic', rapport: 'Rapport', correspondance: 'Correspondance', autre: 'Autre',
};

const ACCENT: Record<string, { bg: string; text: string }> = {
  photo:             { bg: 'var(--cat-4-soft)',  text: 'var(--cat-4)' },
  plan:              { bg: 'var(--cat-1-soft)',  text: 'var(--cat-1)' },
  devis:             { bg: 'var(--cat-7-soft)',  text: 'var(--cat-7)' },
  facture:           { bg: 'var(--cat-2-soft)',  text: 'var(--cat-2)' },
  attestation:       { bg: 'var(--cat-9-soft)',  text: 'var(--cat-9)' },
  extrait_cadastral: { bg: 'var(--cat-3-soft)',  text: 'var(--cat-3)' },
  cerfa:             { bg: 'var(--cat-11-soft)', text: 'var(--cat-11)' },
  arrete:            { bg: 'var(--cat-5-soft)',  text: 'var(--cat-5)' },
  diagnostic:        { bg: 'var(--cat-10-soft)', text: 'var(--cat-10)' },
  rapport:           { bg: 'var(--muted)',       text: 'var(--gray-fg)' },
  correspondance:    { bg: 'var(--cat-12-soft)', text: 'var(--cat-12)' },
  autre:             { bg: 'var(--muted)',       text: 'var(--gray-fg)' },
};

export function typeIcon(type: DocumentType): IconComponent {
  return ICONS[type] ?? IconDocument;
}
export function typeLabel(type: DocumentType): string {
  return LABELS[type] ?? type;
}
export function typeAccent(type: DocumentType): { bg: string; text: string } {
  return ACCENT[type] ?? ACCENT.autre;
}

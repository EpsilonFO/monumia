import {
  IconDevis, IconImage, IconArchive, IconParchemin, IconRegle, IconDiagnostic,
  IconPlan, IconCadastre, IconCourrier, IconDocument, IconDocumentValide,
  IconChantier, IconSubvention, IconMaison, IconInstitution, IconLivre, IconTendance,
  type IconComponent,
} from '@/components/icons';
import type { DocumentType } from '@/types';

/**
 * Les types de document, à UN endroit : libellé, famille, icône et couleur.
 * L'ordre des familles et des types est celui de la maquette « Mes documents »
 * (yaml paul) : il sert tel quel au select « Tous les types » et aux pilules de
 * la fenêtre d'ajout.
 */
export interface FamilleTypes {
  nom: string;
  types: DocumentType[];
}

export const FAMILLES_TYPES: FamilleTypes[] = [
  { nom: 'Le monument', types: ['photo', 'plan', 'extrait_cadastral', 'arrete', 'diagnostic', 'rapport'] },
  { nom: 'Les travaux', types: ['devis', 'facture', 'autorisation_urbanisme'] },
  {
    nom: 'Administratif et financier',
    types: ['cerfa', 'attestation', 'rib', 'titre_propriete', 'deliberation', 'statuts', 'plan_financement'],
  },
  { nom: 'Échanges et divers', types: ['correspondance', 'autre'] },
];

/** Tous les types, dans l'ordre des familles. */
export const TYPES_DOCUMENT: DocumentType[] = FAMILLES_TYPES.flatMap((f) => f.types);

const LABELS: Record<DocumentType, string> = {
  photo: 'Photo', plan: 'Plan', devis: 'Devis', facture: 'Facture',
  attestation: 'Attestation', extrait_cadastral: 'Extrait cadastral', cerfa: 'CERFA',
  arrete: 'Arrêté', diagnostic: 'Diagnostic', rapport: 'Rapport', correspondance: 'Correspondance', autre: 'Autre',
  autorisation_urbanisme: "Autorisation d'urbanisme", rib: 'RIB', titre_propriete: 'Titre de propriété',
  deliberation: 'Délibération', statuts: 'Statuts', plan_financement: 'Plan de financement',
};

const ICONS: Record<DocumentType, IconComponent> = {
  photo: IconImage, plan: IconPlan, devis: IconDevis, facture: IconDevis,
  attestation: IconDocumentValide, extrait_cadastral: IconCadastre, cerfa: IconDocumentValide,
  arrete: IconRegle, diagnostic: IconDiagnostic, rapport: IconParchemin, correspondance: IconCourrier, autre: IconArchive,
  autorisation_urbanisme: IconChantier, rib: IconSubvention, titre_propriete: IconMaison,
  deliberation: IconInstitution, statuts: IconLivre, plan_financement: IconTendance,
};

const ACCENT: Record<DocumentType, { bg: string; text: string }> = {
  photo:                  { bg: 'var(--cat-4-soft)',  text: 'var(--cat-4)' },
  plan:                   { bg: 'var(--cat-1-soft)',  text: 'var(--cat-1)' },
  devis:                  { bg: 'var(--cat-7-soft)',  text: 'var(--cat-7)' },
  facture:                { bg: 'var(--cat-2-soft)',  text: 'var(--cat-2)' },
  attestation:            { bg: 'var(--cat-9-soft)',  text: 'var(--cat-9)' },
  extrait_cadastral:      { bg: 'var(--cat-3-soft)',  text: 'var(--cat-3)' },
  cerfa:                  { bg: 'var(--cat-11-soft)', text: 'var(--cat-11)' },
  arrete:                 { bg: 'var(--cat-5-soft)',  text: 'var(--cat-5)' },
  diagnostic:             { bg: 'var(--cat-10-soft)', text: 'var(--cat-10)' },
  rapport:                { bg: 'var(--muted)',       text: 'var(--gray-fg)' },
  correspondance:         { bg: 'var(--cat-12-soft)', text: 'var(--cat-12)' },
  autre:                  { bg: 'var(--muted)',       text: 'var(--gray-fg)' },
  autorisation_urbanisme: { bg: 'var(--cat-6-soft)',  text: 'var(--cat-6)' },
  rib:                    { bg: 'var(--cat-8-soft)',  text: 'var(--cat-8)' },
  titre_propriete:        { bg: 'var(--cat-3-soft)',  text: 'var(--cat-3)' },
  deliberation:           { bg: 'var(--cat-5-soft)',  text: 'var(--cat-5)' },
  statuts:                { bg: 'var(--cat-11-soft)', text: 'var(--cat-11)' },
  plan_financement:       { bg: 'var(--cat-7-soft)',  text: 'var(--cat-7)' },
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

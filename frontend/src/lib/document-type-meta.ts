import {
  Receipt, Image, FileSpreadsheet, FileArchive, ScrollText, Scale, FileSearch,
  PenTool, FileText, Stamp, FileBadge, ClipboardList, type LucideIcon,
} from 'lucide-react';
import type { DocumentType } from '@/types';

const ICONS: Record<string, LucideIcon> = {
  photo: Image, plan: FileSpreadsheet, devis: ClipboardList, facture: Receipt,
  attestation: FileBadge, extrait_cadastral: FileSpreadsheet, cerfa: Stamp,
  arrete: Scale, diagnostic: FileSearch, rapport: ScrollText, correspondance: PenTool, autre: FileArchive,
};

const LABELS: Record<string, string> = {
  photo: 'Photo', plan: 'Plan', devis: 'Devis', facture: 'Facture',
  attestation: 'Attestation', extrait_cadastral: 'Extrait cadastral', cerfa: 'CERFA',
  arrete: 'Arrêté', diagnostic: 'Diagnostic', rapport: 'Rapport', correspondance: 'Correspondance', autre: 'Autre',
};

const ACCENT: Record<string, { bg: string; text: string }> = {
  photo: { bg: '#F3E8FF', text: '#7C3AED' },
  plan: { bg: '#E8EAF6', text: '#1A237E' },
  devis: { bg: '#FEF3C7', text: '#92400E' },
  facture: { bg: '#FBF0EC', text: '#C75B3A' },
  attestation: { bg: '#ECFDF5', text: '#065F46' },
  extrait_cadastral: { bg: '#E0F2F1', text: '#00695C' },
  cerfa: { bg: '#E0F7FA', text: '#006064' },
  arrete: { bg: '#FFEBEE', text: '#B71C1C' },
  diagnostic: { bg: '#E8EAF6', text: '#283593' },
  rapport: { bg: '#F1F5F9', text: '#334155' },
  correspondance: { bg: '#FCE4EC', text: '#880E4F' },
  autre: { bg: '#F3F4F6', text: '#374151' },
};

export function typeIcon(type: DocumentType): LucideIcon {
  return ICONS[type] ?? FileText;
}
export function typeLabel(type: DocumentType): string {
  return LABELS[type] ?? type;
}
export function typeAccent(type: DocumentType): { bg: string; text: string } {
  return ACCENT[type] ?? ACCENT.autre;
}

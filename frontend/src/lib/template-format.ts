import i18n from '@/i18n';

/**
 * Présentation d'un format de fichier (badge) à partir de l'extension.
 * Volontairement permissif : les modèles peuvent être de types très variés.
 * Une extension inconnue retombe sur un libellé générique « Fichier ».
 */
export interface FormatBadge {
  label: string;
  /** Classes Tailwind (fond + texte) du badge. */
  className: string;
}

const FORMAT_MAP: Record<string, FormatBadge> = {
  pdf: { label: 'PDF', className: 'bg-cat-8-soft text-cat-8' },
  doc: { label: 'DOC', className: 'bg-info-muted text-info' },
  docx: { label: 'DOCX', className: 'bg-info-muted text-info' },
  odt: { label: 'ODT', className: 'bg-info-muted text-info' },
  xls: { label: 'XLS', className: 'bg-success-muted text-success' },
  xlsx: { label: 'XLSX', className: 'bg-success-muted text-success' },
  ods: { label: 'ODS', className: 'bg-success-muted text-success' },
  csv: { label: 'CSV', className: 'bg-success-muted text-success' },
  ppt: { label: 'PPT', className: 'bg-cat-2-soft text-cat-2' },
  pptx: { label: 'PPTX', className: 'bg-cat-2-soft text-cat-2' },
  md: { label: 'MD', className: 'bg-muted text-muted-foreground' },
  txt: { label: 'TXT', className: 'bg-muted text-muted-foreground' },
  rtf: { label: 'RTF', className: 'bg-muted text-muted-foreground' },
  zip: { label: 'ZIP', className: 'bg-warning-muted text-warning' },
  jpg: { label: 'JPG', className: 'bg-cat-violet-soft text-cat-violet' },
  jpeg: { label: 'JPG', className: 'bg-cat-violet-soft text-cat-violet' },
  png: { label: 'PNG', className: 'bg-cat-violet-soft text-cat-violet' },
};

export function formatBadge(extension?: string): FormatBadge {
  const ext = extension?.toLowerCase().replace(/^\./, '') ?? '';
  return FORMAT_MAP[ext] ?? { label: ext ? ext.toUpperCase() : i18n.t('core:templateFormat.fichier'), className: 'bg-muted text-muted-foreground' };
}

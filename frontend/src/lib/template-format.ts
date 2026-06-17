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
  pdf: { label: 'PDF', className: 'bg-rose-100 text-rose-700' },
  doc: { label: 'DOC', className: 'bg-blue-100 text-blue-700' },
  docx: { label: 'DOCX', className: 'bg-blue-100 text-blue-700' },
  odt: { label: 'ODT', className: 'bg-blue-100 text-blue-700' },
  xls: { label: 'XLS', className: 'bg-emerald-100 text-emerald-700' },
  xlsx: { label: 'XLSX', className: 'bg-emerald-100 text-emerald-700' },
  ods: { label: 'ODS', className: 'bg-emerald-100 text-emerald-700' },
  csv: { label: 'CSV', className: 'bg-emerald-100 text-emerald-700' },
  ppt: { label: 'PPT', className: 'bg-orange-100 text-orange-700' },
  pptx: { label: 'PPTX', className: 'bg-orange-100 text-orange-700' },
  md: { label: 'MD', className: 'bg-slate-100 text-slate-700' },
  txt: { label: 'TXT', className: 'bg-slate-100 text-slate-700' },
  rtf: { label: 'RTF', className: 'bg-slate-100 text-slate-700' },
  zip: { label: 'ZIP', className: 'bg-amber-100 text-amber-700' },
  jpg: { label: 'JPG', className: 'bg-violet-100 text-violet-700' },
  jpeg: { label: 'JPG', className: 'bg-violet-100 text-violet-700' },
  png: { label: 'PNG', className: 'bg-violet-100 text-violet-700' },
};

export function formatBadge(extension?: string): FormatBadge {
  const ext = extension?.toLowerCase().replace(/^\./, '') ?? '';
  return FORMAT_MAP[ext] ?? { label: ext ? ext.toUpperCase() : 'Fichier', className: 'bg-slate-100 text-slate-700' };
}

import { FileText, Image, FileSpreadsheet, File, FolderOpen } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatFileSize } from '@/lib/format-utils';
import { formatDate } from '@/lib/date-utils';
import { cn } from '@/lib/utils';
import type { Document } from '@/types';

interface DocumentCardProps {
  document: Document;
  dossierNames?: Record<string, string>;
}

const typeIcons: Record<string, typeof FileText> = {
  photo: Image,
  plan: FileSpreadsheet,
  devis: FileText,
  facture: FileText,
  attestation: FileText,
  extrait_cadastral: FileText,
  cerfa: FileText,
  arrete: FileText,
  diagnostic: FileText,
  rapport: FileText,
  correspondance: FileText,
  autre: File,
};

const typeLabels: Record<string, string> = {
  photo: 'Photo',
  plan: 'Plan',
  devis: 'Devis',
  facture: 'Facture',
  attestation: 'Attestation',
  extrait_cadastral: 'Extrait cadastral',
  cerfa: 'CERFA',
  arrete: 'Arrêté',
  diagnostic: 'Diagnostic',
  rapport: 'Rapport',
  correspondance: 'Correspondance',
  autre: 'Autre',
};

const typeBg: Record<string, string> = {
  photo: 'bg-violet-50',
  plan: 'bg-blue-50',
  devis: 'bg-amber-50',
  facture: 'bg-orange-50',
  attestation: 'bg-green-50',
  extrait_cadastral: 'bg-teal-50',
  cerfa: 'bg-cyan-50',
  arrete: 'bg-red-50',
  diagnostic: 'bg-indigo-50',
  rapport: 'bg-slate-50',
  correspondance: 'bg-pink-50',
  autre: 'bg-gray-50',
};

const typeIconColor: Record<string, string> = {
  photo: 'text-violet-400',
  plan: 'text-blue-400',
  devis: 'text-amber-400',
  facture: 'text-orange-400',
  attestation: 'text-green-400',
  extrait_cadastral: 'text-teal-400',
  cerfa: 'text-cyan-400',
  arrete: 'text-red-400',
  diagnostic: 'text-indigo-400',
  rapport: 'text-slate-400',
  correspondance: 'text-pink-400',
  autre: 'text-gray-400',
};

export function DocumentCard({ document, dossierNames }: DocumentCardProps) {
  const Icon = typeIcons[document.type] ?? File;

  const linkedDossiers = dossierNames
    ? document.dossiersUtilises.map((id) => dossierNames[id]).filter(Boolean)
    : [];

  return (
    <Card className="hover:shadow-md transition-shadow overflow-hidden flex flex-col">
      {/* Preview */}
      {
        <div
          className={cn(
            'h-24 flex items-center justify-center',
            typeBg[document.type] ?? 'bg-muted'
          )}
        >
          <Icon className={cn('h-10 w-10', typeIconColor[document.type] ?? 'text-muted-foreground')} />
        </div>
      }

      <CardContent className="p-4 space-y-3 flex-1 flex flex-col">
        <div>
          <p className="text-sm font-medium leading-tight line-clamp-2">
            {document.nom}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {document.nomFichier}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className="text-xs">
            {typeLabels[document.type] ?? document.type}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {formatFileSize(document.tailleFichier)}
          </span>
          <span className="text-xs text-muted-foreground">
            {formatDate(document.dateUpload)}
          </span>
        </div>

        {document.description && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {document.description}
          </p>
        )}

        {/* Dossiers associés */}
        {linkedDossiers.length > 0 && (
          <div className="mt-auto pt-2 border-t space-y-1">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium flex items-center gap-1">
              <FolderOpen className="h-3 w-3" />
              Dossiers associés
            </p>
            {linkedDossiers.map((name) => (
              <p key={name} className="text-xs text-foreground truncate">
                {name}
              </p>
            ))}
          </div>
        )}

        {document.dossiersUtilises.length > 0 && linkedDossiers.length === 0 && (
          <p className="text-xs text-muted-foreground mt-auto pt-2 border-t">
            Utilisé dans {document.dossiersUtilises.length} dossier{document.dossiersUtilises.length > 1 ? 's' : ''}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

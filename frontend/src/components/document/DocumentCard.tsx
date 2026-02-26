import { FileText, Image, FileSpreadsheet, File, Download, Tag } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatFileSize } from '@/lib/format-utils';
import { formatDate } from '@/lib/date-utils';
import type { Document } from '@/types';

interface DocumentCardProps {
  document: Document;
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

export function DocumentCard({ document }: DocumentCardProps) {
  const Icon = typeIcons[document.type] ?? File;

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <Icon className="h-5 w-5 text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium leading-tight truncate">
              {document.nom}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {document.nomFichier}
            </p>
          </div>
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

        {document.tags.length > 0 && (
          <div className="flex items-center gap-1 flex-wrap">
            <Tag className="h-3 w-3 text-muted-foreground" />
            {document.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="text-[10px] px-1.5 py-0">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {document.dossiersUtilises.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Utilisé dans {document.dossiersUtilises.length} dossier{document.dossiersUtilises.length > 1 ? 's' : ''}
          </p>
        )}

        {document.description && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {document.description}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

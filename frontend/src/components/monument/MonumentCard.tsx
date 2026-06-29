import { Link, useNavigate } from 'react-router';
import { MapPin, Shield, ChevronRight, Compass, FolderOpen } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useAideStore } from '@/stores/useAideStore';
import { ROUTES } from '@/constants/routes';
import type { Monument } from '@/types';

interface MonumentCardProps {
  monument: Monument;
}

const protectionLabels: Record<string, string> = {
  classe: 'Classé MH', inscrit: 'Inscrit MH', abords: 'Abords MH', spr: 'SPR', non_protege: 'Non protégé',
};

const etatColors: Record<string, { bg: string; text: string }> = {
  bon: { bg: 'var(--success-muted)', text: 'var(--success)' },
  moyen: { bg: 'var(--warning-muted)', text: 'var(--warning)' },
  mauvais: { bg: 'var(--warning-muted)', text: 'var(--accent)' },
  peril: { bg: 'var(--destructive-muted)', text: 'var(--destructive)' },
};

const etatLabels: Record<string, string> = {
  bon: 'Bon état', moyen: 'État moyen', mauvais: 'Mauvais état', peril: 'En péril',
};

export function MonumentCard({ monument }: MonumentCardProps) {
  const navigate = useNavigate();
  const hasDiagnostic = useAideStore((s) => !!s.diagnosticsByMonument[monument.id]);
  const etat = etatColors[monument.etatConservation] ?? etatColors.moyen;

  const handleDossierClick = (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    navigate(`${ROUTES.DOSSIERS}?monument=${monument.id}`);
  };

  const handleDiagnosticClick = (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    navigate(`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=aides`);
  };

  return (
    <Link to={ROUTES.MONUMENT_DETAIL(monument.id)}>
      <div className="group bg-card rounded-xl border border-border overflow-hidden transition-all duration-200 hover:shadow-md hover:shadow-black/[0.03] hover:border-border">
        {/* Header */}
        <div className="px-5 pt-5 pb-3">
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3
              className="text-[16px] font-normal text-foreground leading-tight line-clamp-2 h-[2.5em]"
              style={{ fontFamily: "'Cormorant Garamond', serif" }}
            >
              {monument.nom}
            </h3>
            <ChevronRight className="h-4 w-4 text-border group-hover:text-destructive transition-colors shrink-0 mt-0.5" />
          </div>
          <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <MapPin className="h-3 w-3 shrink-0" strokeWidth={1.8} />
            <span>{monument.commune}{monument.departement ? ` (${monument.departement})` : ''}</span>
          </div>
        </div>

        {/* Badges */}
        <div className="px-5 pb-3 flex items-center gap-2 flex-wrap">
          <Badge className="text-[10px] font-semibold border-0 gap-1 bg-secondary text-primary">
            <Shield className="h-3 w-3" strokeWidth={1.8} />
            {protectionLabels[monument.protection] ?? monument.protection}
          </Badge>
          <Badge className="text-[10px] font-semibold border-0" style={{ background: etat.bg, color: etat.text }}>
            {etatLabels[monument.etatConservation] ?? monument.etatConservation}
          </Badge>
        </div>

        {/* Progress */}
        <div className="px-5 pb-3">
          <div className="flex items-center justify-between text-[11px] mb-1">
            <span className="text-muted-foreground">Fiche complétée</span>
            <span className="font-semibold text-foreground">{monument.completionPercentage}%</span>
          </div>
          <Progress value={monument.completionPercentage} className="h-1" />
        </div>

        {/* Actions */}
        <div className="px-5 pb-4 flex gap-2">
          <button
            onClick={handleDossierClick}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[12px] font-medium border border-border rounded-lg text-gray-fg hover:bg-muted transition-colors"
          >
            <FolderOpen className="h-3.5 w-3.5" strokeWidth={1.8} />
            Dossiers
          </button>
          <button
            onClick={handleDiagnosticClick}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[12px] font-semibold rounded-lg transition-all duration-200 ${
              hasDiagnostic
                ? 'border border-border text-gray-fg bg-transparent hover:bg-muted'
                : 'bg-primary text-white hover:opacity-90'
            }`}
          >
            <Compass className="h-3.5 w-3.5" strokeWidth={1.8} />
            {hasDiagnostic ? 'Diagnostic' : 'Diagnostiquer'}
          </button>
        </div>
      </div>
    </Link>
  );
}

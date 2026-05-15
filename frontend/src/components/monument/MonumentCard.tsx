import { Link, useNavigate } from 'react-router';
import { MapPin, Shield, AlertTriangle, ChevronRight, Compass, FolderOpen } from 'lucide-react';
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
  bon: { bg: '#ECFDF5', text: '#065F46' },
  moyen: { bg: '#FEF3C7', text: '#92400E' },
  mauvais: { bg: '#FBF0EC', text: '#C75B3A' },
  peril: { bg: '#FFEBEE', text: '#B71C1C' },
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
      <div className="group bg-white rounded-xl border border-[#E4E2DC]/80 overflow-hidden transition-all duration-200 hover:shadow-md hover:shadow-black/[0.03] hover:border-[#E4E2DC]">
        {/* Header */}
        <div className="px-5 pt-5 pb-3">
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3
              className="text-[16px] font-normal text-[#1B1E2E] leading-tight line-clamp-2 h-[2.5em]"
              style={{ fontFamily: "'Cormorant Garamond', serif" }}
            >
              {monument.nom}
            </h3>
            <ChevronRight className="h-4 w-4 text-[#E4E2DC] group-hover:text-[#C75B3A] transition-colors shrink-0 mt-0.5" />
          </div>
          <div className="flex items-center gap-1.5 text-[12px] text-[#8E92A4]">
            <MapPin className="h-3 w-3 shrink-0" strokeWidth={1.8} />
            <span>{monument.commune}{monument.departement ? ` (${monument.departement})` : ''}</span>
          </div>
        </div>

        {/* Badges */}
        <div className="px-5 pb-3 flex items-center gap-2 flex-wrap">
          <Badge className="text-[10px] font-semibold border-0 gap-1 bg-[#E8EAF6] text-[#1A237E]">
            <Shield className="h-3 w-3" strokeWidth={1.8} />
            {protectionLabels[monument.protection] ?? monument.protection}
          </Badge>
          <Badge className="text-[10px] font-semibold border-0" style={{ background: etat.bg, color: etat.text }}>
            {monument.urgenceTravaux === 'critique' && <AlertTriangle className="h-3 w-3 mr-0.5" />}
            {etatLabels[monument.etatConservation] ?? monument.etatConservation}
          </Badge>
        </div>

        {/* Progress */}
        <div className="px-5 pb-3">
          <div className="flex items-center justify-between text-[11px] mb-1">
            <span className="text-[#8E92A4]">Fiche complétée</span>
            <span className="font-semibold text-[#1B1E2E]">{monument.completionPercentage}%</span>
          </div>
          <Progress value={monument.completionPercentage} className="h-1" />
        </div>

        {/* Actions */}
        <div className="px-5 pb-4 flex gap-2">
          <button
            onClick={handleDossierClick}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[12px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors"
          >
            <FolderOpen className="h-3.5 w-3.5" strokeWidth={1.8} />
            Dossiers
          </button>
          <button
            onClick={handleDiagnosticClick}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[12px] font-semibold rounded-lg transition-all duration-200 ${
              hasDiagnostic
                ? 'border border-[#E4E2DC] text-[#5C6178] bg-transparent hover:bg-[#F8F7F4]'
                : 'bg-[#1A237E] text-white hover:opacity-90'
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

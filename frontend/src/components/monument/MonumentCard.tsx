import { Link, useNavigate } from 'react-router';
import { MapPin, Shield, AlertTriangle, ChevronRight, Sparkles, FileText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { useDossierStore } from '@/stores/useDossierStore';
import { ROUTES } from '@/constants/routes';
import type { Monument } from '@/types';

interface MonumentCardProps {
  monument: Monument;
}

const protectionLabels: Record<string, string> = {
  classe: 'Classé MH',
  inscrit: 'Inscrit MH',
  abords: 'Abords MH',
  spr: 'SPR',
  non_protege: 'Non protégé',
};

const etatColors: Record<string, string> = {
  bon: 'bg-green-100 text-green-800',
  moyen: 'bg-yellow-100 text-yellow-800',
  mauvais: 'bg-orange-100 text-orange-800',
  peril: 'bg-red-100 text-red-800',
};

const etatLabels: Record<string, string> = {
  bon: 'Bon état',
  moyen: 'État moyen',
  mauvais: 'Mauvais état',
  peril: 'En péril',
};

export function MonumentCard({ monument }: MonumentCardProps) {
  const navigate = useNavigate();
  const hasDossiers = useDossierStore((s) =>
    s.dossiers.some((d) => d.monumentId === monument.id)
  );

  const handleActionClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (hasDossiers) {
      navigate(`${ROUTES.DOSSIERS}?monument=${monument.id}`);
    } else {
      navigate(`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=dossiers`);
    }
  };

  return (
    <Link to={ROUTES.MONUMENT_DETAIL(monument.id)}>
      <Card className="hover:shadow-md hover:border-primary/30 transition-all group">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-base leading-tight">
              {monument.nom}
            </CardTitle>
            <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0 mt-0.5" />
          </div>
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <MapPin className="h-3.5 w-3.5 shrink-0" />
            <span>{monument.commune} ({monument.departement})</span>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="gap-1">
              <Shield className="h-3 w-3" />
              {protectionLabels[monument.protection] ?? monument.protection}
            </Badge>
            <Badge className={etatColors[monument.etatConservation] ?? ''}>
              {monument.urgenceTravaux === 'critique' && (
                <AlertTriangle className="h-3 w-3 mr-1" />
              )}
              {etatLabels[monument.etatConservation] ?? monument.etatConservation}
            </Badge>
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Fiche complétée</span>
              <span className="font-medium">{monument.completionPercentage} %</span>
            </div>
            <Progress value={monument.completionPercentage} className="h-1.5" />
          </div>

          <Button
            variant={hasDossiers ? 'outline' : 'default'}
            size="sm"
            className="w-full"
            onClick={handleActionClick}
          >
            {hasDossiers ? (
              <>
                <FileText className="h-4 w-4 mr-2" />
                Voir mon dossier
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                Lancer un diagnostic
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    </Link>
  );
}

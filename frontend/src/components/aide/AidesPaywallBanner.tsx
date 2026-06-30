import { Link, useLocation } from 'react-router';
import { IconVerrou, IconAccompagnement } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { formatCurrency } from '@/lib/format-utils';

interface AidesPaywallBannerProps {
  montantTotal: number;
  nombreAides: number;
  nombreAidesAvecTaux?: number;
}

export function AidesPaywallBanner({ montantTotal, nombreAides, nombreAidesAvecTaux = 0 }: AidesPaywallBannerProps) {
  const { pathname } = useLocation();

  const montantLine = montantTotal > 0
    ? <>Jusqu'à <span className="font-semibold">{formatCurrency(montantTotal)}</span> récupérables{nombreAidesAvecTaux > 0 && <> + <span className="font-semibold">{nombreAidesAvecTaux}</span> aide{nombreAidesAvecTaux > 1 ? 's' : ''} en %</>} sur <span className="font-semibold">{nombreAides}</span> aides identifiées</>
    : <><span className="font-semibold">{nombreAides}</span> aide{nombreAides > 1 ? 's' : ''} identifiée{nombreAides > 1 ? 's' : ''}{nombreAidesAvecTaux > 0 && <>, dont <span className="font-semibold">{nombreAidesAvecTaux}</span> avec financement en pourcentage</>}</>;

  return (
    <div className="rounded-xl border border-warning bg-warning-muted p-5 flex items-start gap-4">
      <div className="shrink-0 w-10 h-10 rounded-full bg-warning flex items-center justify-center">
        <IconAccompagnement className="h-5 w-5 text-warning-foreground" />
      </div>
      <div className="flex-1 space-y-2">
        <h3 className="text-base font-medium text-foreground">
          {montantLine}
        </h3>
        <p className="text-sm text-muted-foreground">
          Le détail des aides identifiées pour votre monument est masqué. Débloquez-le pour consulter le nom des aides, les organismes, et postuler.
        </p>
        <Button asChild size="sm" className="bg-warning text-warning-foreground hover:opacity-90">
          <Link to="/tarifs" state={{ from: pathname }}>
            <IconVerrou className="h-3.5 w-3.5 mr-1.5" />
            Découvrir les aides
          </Link>
        </Button>
      </div>
    </div>
  );
}

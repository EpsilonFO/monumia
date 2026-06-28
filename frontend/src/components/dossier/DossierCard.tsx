import { Link } from 'react-router';
import { MapPin, Calendar, ChevronRight } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { AideStatutBadge } from '@/components/aide/AideStatutBadge';
import { ROUTES } from '@/constants/routes';
import { formatDate, isUrgent, daysUntil } from '@/lib/date-utils';
import type { Dossier, AideSuiviStatut } from '@/types';
import { C, SERIF } from '@/lib/brand';

// Couleurs catégorielles des monuments — 8 teintes distinctes via tokens de thème.
// Les 3 teintes de catégorie (violet, sarcelle, bordeaux) utilisent des tokens dédiés
// --cat-violet / --cat-teal / --cat-burgundy, avec variantes dark-mode correspondantes.
const MONUMENT_COLORS = [
  C.blue,
  C.orange,
  'var(--color-success)',
  'var(--color-cat-violet)',
  'var(--color-warning)',
  'var(--color-cat-teal)',
  'var(--color-cat-burgundy)',
  'var(--color-blue-light)',
];

interface DossierCardProps {
  dossier: Dossier;
  monumentColor?: string;
}

export function DossierCard({ dossier, monumentColor }: DossierCardProps) {
  const monuments = useMonumentStore((s) => s.monuments);
  const monument = monuments.find((m) => m.id === dossier.monumentId);

  // Avancement du dossier (à défaut de suivi enregistré : « À faire »).
  const suivi = useSuiviStore((s) =>
    s.suivis.find((x) => x.monumentId === dossier.monumentId && x.aideId === dossier.aideId),
  );
  const statut: AideSuiviStatut = suivi?.statut ?? 'a_faire';

  const nextDeadline = dossier.echeances.find((e) => !e.accomplie);
  const fournis = dossier.checklist.filter((c) => c.statut === 'fourni').length;
  const manquants = dossier.checklist.filter((c) => c.statut === 'manquant').length;
  const enAttente = dossier.checklist.filter((c) => c.statut === 'en_attente').length;
  const piecesTotal = dossier.checklist.length;

  const [aideName] = dossier.titre.split(' — ');
  const color = monumentColor ?? C.blue;

  return (
    <Link to={ROUTES.PROJET_DOSSIER(dossier.monumentId, dossier.id)} className="block h-full">
      <div
        className="group relative bg-card rounded-xl border border-border/80 overflow-hidden transition-all duration-200 hover:shadow-md hover:shadow-black/[0.03] hover:border-border flex flex-col h-full"
        style={{ borderLeft: `4px solid ${color}` }}
      >

        <div className="px-5 pt-5 pb-3">
          <div className="mb-2.5 flex items-center justify-between gap-2">
            {monument ? (
              <span
                className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
                style={{ background: `${color}14`, color }}
              >
                <MapPin className="h-3 w-3 shrink-0" strokeWidth={2} />
                <span className="truncate max-w-[140px]">{monument.nom}</span>
              </span>
            ) : (
              <span />
            )}
            <AideStatutBadge statut={statut} />
          </div>
          <div className="flex items-start justify-between gap-2">
            <h3
              className="text-[16px] font-normal text-foreground leading-tight line-clamp-2 min-h-[2.5em]"
              style={{ fontFamily: SERIF }}
            >
              {aideName}
            </h3>
            <ChevronRight className="h-4 w-4 text-border group-hover:text-accent transition-colors shrink-0 mt-0.5" />
          </div>
          {monument?.commune && (
            <div className="mt-1.5 text-[12px] text-muted-foreground truncate">
              {monument.commune}
            </div>
          )}
        </div>

        {piecesTotal > 0 && (
          <div className="px-5 pb-3 flex items-center gap-4 text-[12px]">
            {fournis > 0 && (
              <span className="flex items-center gap-1.5 text-success">
                <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0" />
                {fournis} fourni{fournis > 1 ? 's' : ''}
              </span>
            )}
            {manquants > 0 && (
              <span className="flex items-center gap-1.5 text-destructive">
                <span className="w-1.5 h-1.5 rounded-full bg-destructive shrink-0" />
                {manquants} manquant{manquants > 1 ? 's' : ''}
              </span>
            )}
            {enAttente > 0 && (
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <span className="w-1.5 h-1.5 rounded-full bg-border shrink-0" />
                {enAttente} en attente
              </span>
            )}
          </div>
        )}

        <div className="px-5 pb-4 space-y-2 mt-auto">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-muted-foreground">Progression</span>
            <span className="font-semibold text-gray-fg tabular-nums">{dossier.progressionPourcentage}%</span>
          </div>
          <Progress value={dossier.progressionPourcentage} className="h-1" />

          {nextDeadline && (
            <div className={`flex items-center gap-1.5 text-[11px] pt-0.5 ${isUrgent(nextDeadline.date) ? 'text-destructive font-medium' : 'text-muted-foreground'}`}>
              <Calendar className="h-3 w-3 shrink-0" strokeWidth={1.8} />
              <span className="truncate">{nextDeadline.label} · {formatDate(nextDeadline.date)}</span>
              {isUrgent(nextDeadline.date) && (
                <span className="ml-auto bg-destructive-muted text-destructive text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0">
                  J-{daysUntil(nextDeadline.date)}
                </span>
              )}
            </div>
          )}
        </div>

      </div>
    </Link>
  );
}

export { MONUMENT_COLORS };

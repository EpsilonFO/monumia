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

const MONUMENT_COLORS = [
  C.blue,
  C.orange,
  '#065F46',
  '#7C3AED',
  '#92400E',
  '#006064',
  '#880E4F',
  '#1565C0',
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
        className="group relative bg-white rounded-xl border border-[#E4E2DC]/80 overflow-hidden transition-all duration-200 hover:shadow-md hover:shadow-black/[0.03] hover:border-[#E4E2DC] flex flex-col h-full"
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
              className="text-[16px] font-normal text-[#222b35] leading-tight line-clamp-2 min-h-[2.5em]"
              style={{ fontFamily: SERIF }}
            >
              {aideName}
            </h3>
            <ChevronRight className="h-4 w-4 text-[#E4E2DC] group-hover:text-[#f17105] transition-colors shrink-0 mt-0.5" />
          </div>
          {monument?.commune && (
            <div className="mt-1.5 text-[12px] text-[#8E92A4] truncate">
              {monument.commune}
            </div>
          )}
        </div>

        {piecesTotal > 0 && (
          <div className="px-5 pb-3 flex items-center gap-4 text-[12px]">
            {fournis > 0 && (
              <span className="flex items-center gap-1.5 text-green-700">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" />
                {fournis} fourni{fournis > 1 ? 's' : ''}
              </span>
            )}
            {manquants > 0 && (
              <span className="flex items-center gap-1.5 text-red-600">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                {manquants} manquant{manquants > 1 ? 's' : ''}
              </span>
            )}
            {enAttente > 0 && (
              <span className="flex items-center gap-1.5 text-[#8E92A4]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#C0BDBA] shrink-0" />
                {enAttente} en attente
              </span>
            )}
          </div>
        )}

        <div className="px-5 pb-4 space-y-2 mt-auto">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-[#8E92A4]">Progression</span>
            <span className="font-semibold text-[#5C6178] tabular-nums">{dossier.progressionPourcentage}%</span>
          </div>
          <Progress value={dossier.progressionPourcentage} className="h-1" />

          {nextDeadline && (
            <div className={`flex items-center gap-1.5 text-[11px] pt-0.5 ${isUrgent(nextDeadline.date) ? 'text-red-600 font-medium' : 'text-[#8E92A4]'}`}>
              <Calendar className="h-3 w-3 shrink-0" strokeWidth={1.8} />
              <span className="truncate">{nextDeadline.label} · {formatDate(nextDeadline.date)}</span>
              {isUrgent(nextDeadline.date) && (
                <span className="ml-auto bg-red-50 text-red-600 text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0">
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

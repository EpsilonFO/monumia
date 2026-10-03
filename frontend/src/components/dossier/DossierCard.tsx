import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { IconLocalisation, IconCalendrier, IconSucces, IconErreur, IconTemps, IconRafraichir } from '@/components/icons';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { ROUTES } from '@/constants/routes';
import { formatDate, isUrgent, daysUntil } from '@/lib/date-utils';
import { progressionDossier } from '@/lib/checklist-progress';
import { AIDE_SUIVI_STATUT_LABELS } from '@/types';
import type { Dossier, AideSuiviStatut } from '@/types';
import { C, SERIF } from '@/lib/brand';

// Couleur pilote de la carte = statut d'avancement. Reprend le code couleur des
// tokens de thème (voir AIDE_STATUT_STYLES) : anneau et pastille partagent la
// même teinte pour un repérage immédiat.
const STATUT_ACCENT: Record<AideSuiviStatut, string> = {
  a_faire:        'var(--muted-foreground)',
  en_preparation: 'var(--info)',
  depose:         'var(--warning)',
  accorde:        'var(--success)',
  refuse:         'var(--destructive)',
};
const STATUT_TINT: Record<AideSuiviStatut, string> = {
  a_faire:        'var(--muted)',
  en_preparation: 'var(--info-muted)',
  depose:         'var(--warning-muted)',
  accorde:        'var(--success-muted)',
  refuse:         'var(--destructive-muted)',
};

// Couleurs catégorielles des monuments — 8 teintes distinctes via tokens de thème.
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

// Couleur de l'anneau = avancement du dossier, pas statut : gris tant que le
// remplissage démarre à peine, orange dès qu'il progresse, vert une fois complet.
// Pas de rouge — un dossier peu rempli n'est pas une erreur, juste un début.
function progressColor(value: number): string {
  if (value >= 100) return C.success;
  if (value >= 34) return C.orange;
  return C.grayMuted;
}

// Anneau de progression — repère visuel principal, grand et lisible. Arc coloré
// selon l'avancement sur une piste gris clair, pourcentage en gras au centre.
function ProgressRing({ value, color }: { value: number; color: string }) {
  const size = 76;
  const stroke = 8;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, value));
  const offset = circ * (1 - clamped / 100);
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 500ms ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[22px] font-bold leading-none tabular-nums" style={{ color: C.ink }}>
          {clamped}
          <span className="text-[14px] font-semibold">%</span>
        </span>
      </div>
    </div>
  );
}

interface DossierCardProps {
  dossier: Dossier;
  monumentColor?: string;
}

export function DossierCard({ dossier }: DossierCardProps) {
  const monuments = useMonumentStore((s) => s.monuments);
  const monument = monuments.find((m) => m.id === dossier.monumentId);

  // Avancement du dossier (à défaut de suivi enregistré : « À faire »).
  const suivi = useSuiviStore((s) =>
    s.suivis.find((x) => x.monumentId === dossier.monumentId && x.aideId === dossier.aideId),
  );
  const statut: AideSuiviStatut = suivi?.statut ?? 'a_faire';
  const accent = STATUT_ACCENT[statut];
  const tint = STATUT_TINT[statut];

  // Une échéance passée ne s'affiche plus (décision du 2026-09-28) : seule la
  // prochaine à venir compte.
  const nextDeadline = dossier.echeances.find((e) => !e.accomplie && daysUntil(e.date) >= 0);
  const urgent = nextDeadline ? isUrgent(nextDeadline.date) : false;
  const fournis = dossier.checklist.filter((c) => c.statut === 'fourni').length;
  const manquants = dossier.checklist.filter((c) => c.statut === 'manquant').length;
  const enAttente = dossier.checklist.filter((c) => c.statut === 'en_attente').length;
  // Pièces reprises automatiquement : elles ne sont ni fournies ni manquantes, et
  // sans pastille dédiée l'utilisateur ne voit pas qu'il a des pièces à vérifier
  // avant d'ouvrir le dossier.
  const repris = dossier.checklist.filter((c) => c.statut === 'repris').length;
  const piecesTotal = dossier.checklist.length;
  const progression = progressionDossier(dossier);

  const [aideName] = dossier.titre.split(' — ');

  return (
    <Link to={ROUTES.PROJET_DOSSIER(dossier.projetId, dossier.id)} className="group block h-full">
      <div className="relative flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div className="flex flex-col gap-4 p-5">
          {/* En-tête : anneau + identité */}
          <div className="flex items-start gap-4">
            <ProgressRing value={progression} color={progressColor(progression)} />
            <div className="min-w-0 flex-1 space-y-1.5">
              {monument && (
                <span
                  className="inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[14px] font-semibold uppercase tracking-wide"
                  style={{ background: tint, color: accent }}
                >
                  <IconLocalisation className="h-3.5 w-3.5 shrink-0" strokeWidth={2} />
                  <span className="truncate">{monument.nom}</span>
                </span>
              )}
              <h3
                className="line-clamp-2 text-[20.5px] font-normal leading-tight text-foreground"
                style={{ fontFamily: SERIF }}
              >
                {aideName}
              </h3>
              {monument?.commune && (
                <div className="truncate text-[15px] text-muted-foreground">{monument.commune}</div>
              )}
            </div>
          </div>

          {/* Statut — pastille franche à point coloré */}
          <span
            className="inline-flex w-fit items-center gap-2 rounded-full px-3 py-1 text-[15.5px] font-semibold"
            style={{ background: tint, color: accent }}
          >
            <span className="h-2 w-2 rounded-full" style={{ background: accent }} />
            {AIDE_SUIVI_STATUT_LABELS[statut]}
          </span>

          {/* Pièces — chips lisibles */}
          {piecesTotal > 0 && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[15px]">
              {fournis > 0 && (
                <span className="flex items-center gap-1.5 font-medium text-success">
                  <IconSucces className="h-4 w-4 shrink-0" strokeWidth={2} />
                  {fournis} fourni{fournis > 1 ? 's' : ''}
                </span>
              )}
              {repris > 0 && (
                <span className="flex items-center gap-1.5 font-medium" style={{ color: C.blue }}>
                  <IconRafraichir className="h-4 w-4 shrink-0" strokeWidth={2} />
                  {repris} à vérifier
                </span>
              )}
              {manquants > 0 && (
                <span className="flex items-center gap-1.5 font-medium text-destructive">
                  <IconErreur className="h-4 w-4 shrink-0" strokeWidth={2} />
                  {manquants} manquant{manquants > 1 ? 's' : ''}
                </span>
              )}
              {enAttente > 0 && (
                <span className="flex items-center gap-1.5 font-medium text-muted-foreground">
                  <span className="h-2 w-2 rounded-full bg-border shrink-0" />
                  {enAttente} en attente
                </span>
              )}
            </div>
          )}

          {/* Échéance */}
          {nextDeadline && (
            <div
              className={`flex items-center gap-2 text-[15px] ${urgent ? 'font-semibold text-destructive' : 'text-muted-foreground'}`}
            >
              {urgent ? (
                <IconTemps className="h-4 w-4 shrink-0" strokeWidth={2} />
              ) : (
                <IconCalendrier className="h-4 w-4 shrink-0" strokeWidth={1.8} />
              )}
              <span className="truncate">
                {nextDeadline.label} · {formatDate(nextDeadline.date)}
              </span>
              {urgent && (
                <span className="ml-auto shrink-0 rounded-md bg-destructive px-2 py-0.5 text-[14px] font-bold text-destructive-foreground">
                  J-{daysUntil(nextDeadline.date)}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Action franche — invitation claire à ouvrir le dossier */}
        <div className="mt-auto px-5 pb-5">
          <span
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-[17px] font-semibold text-white transition-shadow duration-200 group-hover:shadow-md"
            // Le bleu adouci des écrans (ecrans.css), comme les autres boutons de la page.
            style={{ background: 'var(--ecran-bleu, var(--primary))' }}
          >
            Ouvrir le dossier
            <ArrowRight className="h-5 w-5 transition-transform duration-200 group-hover:translate-x-0.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}

export { MONUMENT_COLORS };

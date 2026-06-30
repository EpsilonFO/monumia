import type { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { IconAide, IconTemps, IconSucces, IconHelp, IconErreur } from '@/components/icons';
import { AIDE_CATEGORIES, AIDE_TYPES } from '@/constants/aide-categories';
import { formatCurrency } from '@/lib/format-utils';
import { deadlineLabel } from '@/lib/date-utils';
import { C, SERIF, DEADLINE_TONE } from '@/lib/brand';
import { decodeHtml, getEligibilityStatus } from './AideDetails';
import type { Aide, AideMatchResult } from '@/types';

/**
 * Bandeau d'en-tête « verdict » d'une aide : il répond, d'un seul coup d'œil et
 * en langage simple, aux trois questions d'un propriétaire pressé — « C'est pour
 * moi ? », « Combien je touche ? », « Jusqu'à quand ? » — avant toute lecture.
 */
const VERDICT = {
  eligible: {
    bg: 'bg-success-muted', fg: 'text-success', border: 'border-success/30', Icon: IconSucces,
    title: 'Bonne nouvelle, vous semblez éligible',
    sub: "D'après les informations de votre projet, cette aide est faite pour vous.",
  },
  potential: {
    bg: 'bg-warning-muted', fg: 'text-warning', border: 'border-warning/30', Icon: IconHelp,
    title: 'Vous y êtes presque',
    sub: 'Quelques points restent à vérifier — on vous montre lesquels juste en dessous.',
  },
  'non-eligible': {
    bg: 'bg-destructive-muted', fg: 'text-destructive', border: 'border-destructive/30', Icon: IconErreur,
    title: 'Cette aide ne semble pas correspondre à ce projet',
    sub: "Elle ne colle pas aux caractéristiques que vous avez renseignées.",
  },
} as const;

function deadlinePill(aide: Aide) {
  if (aide.permanent || !aide.dateLimite) {
    return { label: 'Ouvert toute l\'année', tone: null as null | (typeof DEADLINE_TONE)['normal'] };
  }
  const ech = deadlineLabel(aide.dateLimite);
  const tone = DEADLINE_TONE[ech.urgency];
  const label =
    ech.urgency === 'past' ? 'Candidatures closes'
      : ech.urgency === 'normal' ? `À déposer avant le ${ech.text}`
        : ech.text; // « Demain », « Dans 12 jours »…
  return { label, tone };
}

export function AideHero({ aide, matchResult, cta }: {
  aide: Aide;
  matchResult?: AideMatchResult | null;
  cta?: ReactNode;
}) {
  const cat = AIDE_CATEGORIES.find((c) => c.value === aide.categorie);
  const type = AIDE_TYPES.find((t) => t.value === aide.type);
  const status = matchResult ? getEligibilityStatus(matchResult) : null;
  const v = status ? VERDICT[status] : null;
  const { label: echeanceLabel, tone } = deadlinePill(aide);
  const hasMoney = !!(aide.tauxMax || aide.montantMax);

  return (
    <section
      className="relative overflow-hidden rounded-3xl border"
      style={{ borderColor: C.border, background: C.card, boxShadow: 'var(--shadow-card)' }}
    >
      {/* Filigrane de marque — la main qui reçoit l'aide */}
      <IconAide
        size={220}
        className="pointer-events-none absolute -right-10 -top-14 select-none"
        style={{ color: C.blue, opacity: 0.05 }}
        aria-hidden
      />

      <div className="relative space-y-5 p-6 sm:p-8">
        <div className="flex flex-wrap items-center gap-2">
          {cat && <Badge className={cat.color}>{cat.label}</Badge>}
          {type && <span className="text-[12px] font-medium text-muted-foreground">{type.label}</span>}
        </div>

        <div className="space-y-1">
          <h1 className="text-[clamp(1.5rem,3.2vw,2.1rem)] leading-tight" style={{ fontFamily: SERIF, color: C.ink }}>
            {decodeHtml(aide.nomCourt)}
          </h1>
          {aide.nom && aide.nom !== aide.nomCourt && (
            <p className="text-[13px] text-muted-foreground">{decodeHtml(aide.nom)}</p>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-5">
          {v && (
            <div className={`flex items-start gap-3 rounded-2xl border p-4 ${v.bg} ${v.border} ${hasMoney ? 'sm:col-span-3' : 'sm:col-span-5'}`}>
              <v.Icon className={`h-6 w-6 shrink-0 ${v.fg}`} strokeWidth={2} />
              <div className="space-y-0.5">
                <p className={`text-[15px] font-semibold leading-snug ${v.fg}`}>{v.title}</p>
                <p className="text-[13px] leading-snug text-muted-foreground">{v.sub}</p>
              </div>
            </div>
          )}

          {hasMoney && (
            <div
              className={`rounded-2xl border p-4 ${v ? 'sm:col-span-2' : 'sm:col-span-5'}`}
              style={{ borderColor: C.border, background: 'var(--secondary)' }}
            >
              <p className="text-[12px] font-medium text-muted-foreground">Vous pouvez obtenir</p>
              {aide.tauxMax ? (
                <>
                  <p className="leading-none" style={{ fontFamily: SERIF, color: C.blue }}>
                    <span className="text-[34px] font-bold">jusqu'à {aide.tauxMax}&nbsp;%</span>
                  </p>
                  <p className="mt-1.5 text-[13px] leading-snug text-muted-foreground">
                    de vos travaux{aide.montantMax ? `, dans la limite de ${formatCurrency(aide.montantMax)}` : ''}
                    {' '}(base {aide.baseTTC ? 'TTC' : 'HT'})
                  </p>
                </>
              ) : (
                <>
                  <p className="leading-none" style={{ fontFamily: SERIF, color: C.blue }}>
                    <span className="text-[30px] font-bold">{formatCurrency(aide.montantMax!)}</span>
                  </p>
                  <p className="mt-1.5 text-[13px] leading-snug text-muted-foreground">au maximum</p>
                </>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-medium"
            style={tone
              ? { background: tone.tint, color: tone.fg }
              : { background: 'var(--muted)', color: 'var(--muted-foreground)' }}
          >
            <IconTemps className="h-3.5 w-3.5" />
            {echeanceLabel}
          </span>
          {cta}
        </div>
      </div>
    </section>
  );
}

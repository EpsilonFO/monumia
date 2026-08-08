import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { IconVerrou, IconSubvention, IconAide, IconTendance } from '@/components/icons';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { formatCurrency } from '@/lib/format-utils';

interface AidesPaywallBannerProps {
  monumentId: string;
  montantTotal: number;
  nombreAides: number;
  nombreAidesAvecTaux?: number;
}

/**
 * Bandeau au-dessus des aides d'un projet non débloqué.
 *
 * Le parti pris : montrer l'enjeu chiffré en grand, et rester factuel sur ce qui
 * manque. Le montant et le nombre d'aides sont réels — c'est le résultat du
 * diagnostic, seuls les noms des aides sont masqués.
 */
export function AidesPaywallBanner({
  monumentId,
  montantTotal,
  nombreAides,
  nombreAidesAvecTaux = 0,
}: AidesPaywallBannerProps) {
  const facts = [
    montantTotal > 0
      ? { icon: IconSubvention, value: formatCurrency(montantTotal), label: 'récupérables, au mieux' }
      : null,
    {
      icon: IconAide,
      value: String(nombreAides),
      label: `aide${nombreAides > 1 ? 's' : ''} identifiée${nombreAides > 1 ? 's' : ''}`,
    },
    nombreAidesAvecTaux > 0
      ? {
          icon: IconTendance,
          value: String(nombreAidesAvecTaux),
          label: `financée${nombreAidesAvecTaux > 1 ? 's' : ''} en pourcentage`,
        }
      : null,
  ].filter((f): f is { icon: typeof IconAide; value: string; label: string } => f !== null);

  return (
    <div
      className="overflow-hidden rounded-2xl border-[1.5px]"
      style={{ background: C.card, borderColor: C.orange, boxShadow: 'var(--shadow-pop)' }}
    >
      <div className="flex flex-col gap-6 p-6 lg:flex-row lg:items-center lg:gap-8">
        <div className="min-w-0 flex-1 space-y-3">
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-bold uppercase tracking-[0.08em]"
            style={{ background: C.paleOrange, color: C.orange }}
          >
            <IconVerrou className="h-3 w-3" />
            Projet non débloqué
          </span>

          <h3 className="text-[19px] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>
            Votre diagnostic est prêt. Les noms des aides sont masqués.
          </h3>

          <p className="text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
            Vous voyez les montants, les taux, les échéances et vos critères remplis. Débloquez ce
            projet pour découvrir de quelles aides il s’agit, à quel organisme les demander et avec
            quelles pièces.
          </p>
        </div>

        <div className="flex shrink-0 flex-col gap-4 lg:w-80">
          <div
            className="grid gap-3 rounded-xl p-4"
            style={{
              background: C.paleBlue,
              gridTemplateColumns: `repeat(${facts.length}, minmax(0, 1fr))`,
            }}
          >
            {facts.map(({ icon: Icon, value, label }) => (
              <div key={label} className="flex min-w-0 flex-col items-center gap-1 text-center">
                <Icon className="h-5 w-5 shrink-0" style={{ color: C.orange }} strokeWidth={1.8} />
                <span
                  className="text-[15px] font-bold leading-tight tabular-nums"
                  style={{ color: C.ink }}
                >
                  {value}
                </span>
                <span className="text-[10.5px] leading-tight" style={{ color: C.grayMuted }}>
                  {label}
                </span>
              </div>
            ))}
          </div>

          <Link
            to={ROUTES.TARIFS(monumentId)}
            className="group inline-flex w-full items-center justify-center gap-2 rounded-full px-5 py-3 text-[14.5px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5"
            style={{ background: C.orange }}
          >
            Débloquer ce projet
            <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
          </Link>
        </div>
      </div>
    </div>
  );
}

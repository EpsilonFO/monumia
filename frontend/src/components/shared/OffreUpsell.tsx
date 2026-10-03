import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { C } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';

interface OffreUpsellProps {
  /**
   * Ce que l'offre débloquerait, à l'infinitif et sans majuscule : la phrase se
   * lit « L'offre Veille permet de {action}. », avec l'élision (« d'inviter »).
   */
  action: string;
  /** Nom de l'offre à prendre — « Veille » ou « Multi-monuments ». */
  offre: string;
  /** Monument d'où l'on part, pour que « Retour » revienne au bon endroit. */
  monumentId?: string;
}

/**
 * Bandeau discret annonçant ce qu'une offre ouvrirait, à poser DANS un contenu
 * qui reste par ailleurs utilisable.
 *
 * À distinguer de `PaywallOverlay` et `PaywallDialog` : ceux-là remplacent
 * l'accès à un contenu ou à un geste, celui-ci accompagne un contenu ouvert
 * dont une capacité manque. Seul cas aujourd'hui : l'équipe d'un monument
 * après une résiliation — les membres restent gérables, la seule chose perdue
 * est le droit d'en ajouter. Un paywall par-dessus rendrait leur retrait
 * impossible.
 */
export function OffreUpsell({ action, offre, monumentId }: OffreUpsellProps) {
  return (
    <div
      className="flex flex-col gap-3 rounded-2xl border px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
      style={{ background: C.card, borderColor: C.border }}
    >
      {/* Pas de cadenas : le bandeau annonce ce qui s'ouvre, pas ce qui est
          fermé. Sa flèche est portée une seule fois, par le bouton. */}
      <p className="text-[15.5px] leading-relaxed" style={{ color: C.grayFg }}>
        {`L'offre ${offre} permet ${elider(action)}.`}
      </p>
      <Link
        to={ROUTES.TARIFS(monumentId)}
        className="group inline-flex shrink-0 items-center justify-center gap-2 rounded-full px-5 py-2.5 text-[15.5px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5"
        style={{ background: C.orange }}
      >
        {`Découvrir l'offre ${offre}`}
        <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
      </Link>
    </div>
  );
}

/** « de » devant une consonne, « d' » devant une voyelle : « permet d'inviter ». */
function elider(action: string): string {
  return /^[aeiouyàâéèêëîïôûü]/i.test(action) ? `d'${action}` : `de ${action}`;
}

import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { C } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';

interface OffreUpsellProps {
  /**
   * Ce que l'offre débloquerait, à l'infinitif et sans majuscule : « ajouter un
   * second monument ». Chaque variante le met en forme à sa façon — la
   * capitale initiale pour un bouton, une phrase complète pour un bandeau.
   */
  action: string;
  /**
   * Nom de l'offre à prendre — « Veille » ou « Multi-monuments ». Nommée dans
   * le bandeau, où il y a la place de l'expliquer ; absente du bouton, où
   * « Offre Veille pour mener plus de projets » était plus long que le bouton
   * qu'il remplace. Le nom de l'offre, c'est la page Tarifs qui le donne.
   */
  offre: string;
  /** Monument d'où l'on part, pour que « Retour » revienne au bon endroit. */
  monumentId?: string;
  /** `bouton` remplace un bouton d'action ; `bandeau` explique une section absente. */
  variante?: 'bouton' | 'bandeau';
}

/**
 * Ce qui prend la place d'une action que l'offre ne permet pas.
 *
 * Le parti pris : une porte visible plutôt qu'un vide. Un bouton simplement
 * disparu se lit comme une panne — l'utilisateur cherche ce qu'il a mal fait,
 * puis écrit au support. Une porte nommée (« l'offre Veille débloque ceci »)
 * transforme la même limite en information.
 *
 * Les deux SUPPRESSIONS font exception et n'utilisent pas ce composant : elles
 * disparaissent sans un mot. Vendre le droit de supprimer se lit mal, et
 * personne n'arrive sur une fiche dans l'intention d'effacer.
 */
export function OffreUpsell({
  action,
  offre,
  monumentId,
  variante = 'bouton',
}: OffreUpsellProps) {
  if (variante === 'bouton') {
    return (
      <Link
        to={ROUTES.TARIFS(monumentId)}
        // `aria-label` porte ce que le libellé ne dit plus : hors contexte
        // visuel, « Mener plus de projets » ne laisse pas deviner qu'on part
        // vers les tarifs.
        aria-label={`${capitale(action)} : découvrir l'offre ${offre}`}
        className="group inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-[13px] font-semibold transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        style={{ borderColor: C.orange, color: C.orange, background: C.paleOrange }}
      >
        {capitale(action)}
        <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
      </Link>
    );
  }

  return (
    <div
      className="flex flex-col gap-3 rounded-2xl border px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
      style={{ background: C.card, borderColor: C.border }}
    >
      {/* Pas de cadenas : le bandeau annonce ce qui s'ouvre, pas ce qui est
          fermé. Sa flèche est portée une seule fois, par le bouton. */}
      <p className="text-[13.5px] leading-relaxed" style={{ color: C.grayFg }}>
        {`L'offre ${offre} permet de ${action}.`}
      </p>
      <Link
        to={ROUTES.TARIFS(monumentId)}
        className="group inline-flex shrink-0 items-center justify-center gap-2 rounded-full px-5 py-2.5 text-[13.5px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5"
        style={{ background: C.orange }}
      >
        {`Découvrir l'offre ${offre}`}
        <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
      </Link>
    </div>
  );
}

/** Majuscule initiale : `action` arrive à l'infinitif, pour servir les deux variantes. */
function capitale(texte: string): string {
  return texte.charAt(0).toUpperCase() + texte.slice(1);
}

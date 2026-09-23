import { useEffect, useState, type RefObject } from 'react';
import { Link } from 'react-router';

export type EtapeFiche = 'elig' | 'pieces' | 'depot';

const ETAPES: { cle: EtapeFiche; libelle: string }[] = [
  { cle: 'elig', libelle: 'Éligibilité' },
  { cle: 'pieces', libelle: 'Pièces' },
  { cle: 'depot', libelle: 'Dépôt' },
];

export type ActionBarre =
  | { libelle: string; ancre: string }
  | { libelle: string; vers: string }
  | { libelle: string; onClick: () => void };

/**
 * La barre qui descend quand le titre de la page sort de l'écran : le nom de
 * l'aide, où on en est (éligibilité, pièces, dépôt) et l'action suivante. Elle
 * se glisse sous la barre de l'application, qui reste au-dessus.
 */
export function FicheBarre({
  titre,
  sousTitre,
  etape,
  action,
  repere,
}: {
  titre: string;
  sousTitre: string;
  etape: EtapeFiche;
  action: ActionBarre;
  /** Le titre de la page : la barre paraît quand il est passé au-dessus. */
  repere: RefObject<HTMLElement | null>;
}) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = repere.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setVisible(!e.isIntersecting && e.boundingClientRect.top < 120));
    io.observe(el);
    return () => io.disconnect();
  }, [repere]);

  const courante = ETAPES.findIndex((e) => e.cle === etape);
  // Une ancre ne ferait pas défiler en douceur : la zone qui défile est `main`,
  // pas la page.
  const bouton =
    'ancre' in action ? (
      <button
        type="button"
        className="btn btn-main btn-sm"
        onClick={() => document.getElementById(action.ancre)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
      >
        {action.libelle}
      </button>
    ) : 'vers' in action ? (
      <Link className="btn btn-main btn-sm" to={action.vers}>{action.libelle}</Link>
    ) : (
      <button type="button" className="btn btn-main btn-sm" onClick={action.onClick}>{action.libelle}</button>
    );

  return (
    <div className={`fa-sticky${visible ? ' show' : ''}`} aria-hidden={!visible} inert={!visible}>
      <div className="sticky-in">
        <div className="st-t">
          <b>{titre}</b>
          <small>{sousTitre}</small>
        </div>
        <div className="track">
          {ETAPES.map((e, i) => (
            <span key={e.cle} className={i < courante ? 'done' : i === courante ? 'cur' : undefined}>
              {i > 0 && <em />}
              <i />
              {e.libelle}
            </span>
          ))}
        </div>
        {bouton}
      </div>
    </div>
  );
}

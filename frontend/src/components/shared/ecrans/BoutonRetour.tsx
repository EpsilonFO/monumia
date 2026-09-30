import { Link } from 'react-router';
import { Picto } from './Picto';

/**
 * Le carré bleu « retour » posé en tête des pages de détail (monument, projet,
 * aide, dossier), au-dessus du fil d'Ariane quand la page en a un. Il porte
 * son propre `.ec` pour garder le même dessin sur les pages qui ne sont pas des
 * écrans de maquette (fiche d'aide, dossier).
 */
export function BoutonRetour({ to, libelle, className }: { to: string; libelle: string; className?: string }) {
  return (
    <div className={className ? `ec ${className}` : 'ec'}>
      <Link className="back" to={to} aria-label={libelle} title={libelle}>
        <Picto nom="retour" />
      </Link>
    </div>
  );
}

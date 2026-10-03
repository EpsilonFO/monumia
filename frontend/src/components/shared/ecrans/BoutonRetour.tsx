import { useEffect } from 'react';
import { Link } from 'react-router';
import { useRetourStore } from '@/stores/useRetourStore';
import { Picto } from './Picto';

/**
 * Le carré bleu « retour » posé en tête des pages de détail (monument, projet,
 * aide, dossier), au-dessus du fil d'Ariane quand la page en a un. Il porte
 * son propre `.ec` pour garder le même dessin sur les pages qui ne sont pas des
 * écrans de maquette (fiche d'aide, dossier).
 *
 * Sur téléphone, il s'efface au profit de la barre haute, qui reprend la même
 * destination (cf. useRetourStore).
 */
export function BoutonRetour({ to, libelle, className }: { to: string; libelle: string; className?: string }) {
  const poser = useRetourStore((s) => s.poser);
  const retirer = useRetourStore((s) => s.retirer);

  useEffect(() => {
    const retour = { to, libelle };
    poser(retour);
    return () => retirer(retour);
  }, [to, libelle, poser, retirer]);

  return (
    <div className={className ? `ec max-md:hidden ${className}` : 'ec max-md:hidden'}>
      <Link className="back" to={to} aria-label={libelle} title={libelle}>
        <Picto nom="retour" />
      </Link>
    </div>
  );
}

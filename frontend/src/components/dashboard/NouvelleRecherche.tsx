import { useId, type ReactNode } from 'react';
import { Link } from 'react-router';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Picto } from '@/components/shared/ecrans/Picto';
import { monumentNomCourt } from '@/lib/projet-titre';
import { ROUTES } from '@/constants/routes';
import type { NouvelleRecherche } from './useNouvelleRecherche';
// Le menu déroulant reprend celui du choix du lieu de « Mes documents » (`.ec.dmenu`).
import '@/components/document/documents.css';
import './nouvelle-recherche.css';

/**
 * Le bouton orange : un seul monument possible, il y va tout droit ; plusieurs,
 * il demande lequel ; aucun monument enregistré, il mène à la création d'un
 * monument. Rien quand des monuments existent mais qu'aucun n'ouvre ce droit
 * (membre d'une équipe seulement).
 */
export function BoutonNouvelleRecherche({
  recherche,
  nbMonuments,
  className = 'btn b-orange b-lg',
  children,
}: {
  recherche: NouvelleRecherche;
  /** Monuments visibles par l'utilisateur, qu'il puisse y créer un projet ou non. */
  nbMonuments: number;
  className?: string;
  children: ReactNode;
}) {
  const { candidats, lancer } = recherche;
  const contenu = (
    <>
      <Picto nom="loupe" />
      {children}
    </>
  );

  if (nbMonuments === 0) {
    return <Link className={className} to={ROUTES.MONUMENT_NEW}>{contenu}</Link>;
  }
  if (candidats.length === 0) return null;
  if (candidats.length === 1) {
    return <button className={className} type="button" onClick={() => lancer(candidats[0].id)}>{contenu}</button>;
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className={className} type="button" aria-haspopup="menu">{contenu}</button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="ec dmenu nr-menu">
        <DropdownMenuLabel className="nr-k">Pour quel monument ?</DropdownMenuLabel>
        {candidats.map((m) => (
          <DropdownMenuItem key={m.id} onClick={() => lancer(m.id)}>
            <span className="nomlieu">{m.nom}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * La carte orange en pointillé « Un nouveau projet pour l'abbaye ? » : dans la
 * grille des monuments du tableau de bord, en bandeau sous la liste de « Mes
 * monuments » (`bande`). Centrée dans les deux cas, le bouton dessous
 * (demande de Félix, la maquette met le bouton à droite du bandeau).
 *
 * Seulement quand la page montre UN monument : avec plusieurs, chaque carte
 * porte son propre « Lancer une nouvelle recherche », et la carte en pointillé
 * disparaît (demande de Félix du 2026-10-05).
 */
export function CarteNouveauProjet({
  recherche,
  nbMonuments,
  bande = false,
}: {
  recherche: NouvelleRecherche;
  nbMonuments: number;
  bande?: boolean;
}) {
  const id = useId();
  const { candidats } = recherche;
  if (nbMonuments !== 1 || candidats.length !== 1) return null;
  const titre = `Un nouveau projet pour ${monumentNomCourt(candidats[0].nom) ?? 'ce monument'} ?`;
  return (
    <article className={bande ? 'ns ns-band' : 'ns'} aria-labelledby={id}>
      <span className="pl" aria-hidden="true"><Picto nom="plus" /></span>
      <div>
        <h3 id={id}>{titre}</h3>
        <p>Restauration, mise aux normes, compagnie de théâtre, chantier bénévole, exploitation agricole, coworking, et bien d'autres encore !</p>
      </div>
      <BoutonNouvelleRecherche recherche={recherche} nbMonuments={nbMonuments}>
        Lancer une nouvelle recherche
      </BoutonNouvelleRecherche>
    </article>
  );
}

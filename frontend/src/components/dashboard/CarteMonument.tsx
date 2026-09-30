import { Link } from 'react-router';
import { Avancement } from '@/components/shared/ecrans/Avancement';
import { libelleEtape } from '@/lib/avancement';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ROUTES } from '@/constants/routes';
import { monumentPhotoProfil } from '@/lib/monument-photo';
import { projetTitre } from '@/lib/projet-titre';
import type { MonumentStats, ProjectStage } from '@/lib/project-stats';
import type { Monument, Projet } from '@/types';
import './carte-monument.css';

const pluriel = (n: number, mot: string) => `${n} ${mot}${n > 1 ? 's' : ''}`;

/**
 * Un monument sur le tableau de bord et dans « Mes monuments » : sa photo en
 * bannière (la bande bleue à défaut), son nom dessus, puis où en est son projet
 * (le plus avancé s'il en a plusieurs). Toute la carte mène où mène son bouton :
 * le lien du bouton s'étend sur la carte (`.cmon-lien::after`).
 */
export function CarteMonument({
  monument,
  projets,
  stats,
  stage,
}: {
  monument: Monument;
  projets: Projet[];
  stats: MonumentStats | undefined;
  stage: ProjectStage;
}) {
  const lieu = [monument.commune, monument.departement].filter(Boolean).join(', ');
  const photo = monumentPhotoProfil(monument)?.signedUrl ?? null;
  const { rang, action } = libelleEtape(stage);
  const seul = projets.length === 1 ? projets[0] : null;
  const aides = stats?.aidesIdentifiees ?? 0;
  const dossiers = stats?.dossiersActifs ?? 0;

  const bouton =
    projets.length === 0
      ? { to: ROUTES.PROJET_NEW(monument.id), label: 'Créer un projet' }
      : seul
        ? { to: ROUTES.PROJET_DETAIL(seul.id), label: 'Voir les aides' }
        : { to: ROUTES.MONUMENT_DETAIL(monument.id), label: 'Voir les projets' };

  return (
    <article className="cmon">
      <div
        className={photo ? 'cmon-h photo' : 'cmon-h'}
        style={photo ? { backgroundImage: `var(--cmon-voile), url("${photo}")` } : undefined}
      >
        <h3>{monument.nom}</h3>
        {lieu && <p>{lieu}</p>}
      </div>
      <div className="cmon-b">
        <div className="proj">
          <b>{projets.length === 0 ? 'Pas encore de projet' : seul ? projetTitre(seul, monument.nom) : pluriel(projets.length, 'projet')}</b>
          {projets.length > 0 && `${rang} : ${action}`}
        </div>
        <Avancement stage={stage} />
        <div className="cmon-f">
          <span>
            {aides > 0 ? (
              <>
                <b>{pluriel(aides, 'aide')}</b> repérée{aides > 1 ? 's' : ''}
              </>
            ) : (
              'Aucune aide estimée'
            )}
            {dossiers > 0 && (
              <>
                {' · '}
                <b>{pluriel(dossiers, 'dossier')}</b> en cours
              </>
            )}
          </span>
          <Link className="btn b-blue b-sm cmon-lien" to={bouton.to}>
            {bouton.label}
            <Picto nom="fleche" />
          </Link>
        </div>
      </div>
    </article>
  );
}

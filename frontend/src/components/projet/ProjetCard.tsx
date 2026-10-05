import { Link } from 'react-router';
import { Avancement } from '@/components/shared/ecrans/Avancement';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ROUTES } from '@/constants/routes';
import { deadlineLabel } from '@/lib/date-utils';
import { libelleEtape } from '@/lib/avancement';
import { montantTileMode } from '@/lib/project-card-view';
import { projetTitre } from '@/lib/projet-titre';
import { projectStage, type ProjectStats, type ProjectStage } from '@/lib/project-stats';
import type { Projet } from '@/types';

interface ProjetCardProps {
  projet: Projet;
  /** Nom du monument, pour le titre par défaut (« Restaurer le Château de… »). */
  monumentNom?: string;
  stats?: ProjectStats;
  stage?: ProjectStage;
}

/**
 * Le bouton orange dit la prochaine chose à faire (public peu à l'aise : jamais
 * un « Voir » ambigu), et mène à l'onglet de la page projet où elle se fait.
 * Indexé par `reachedIndex` (-1 = rien de commencé).
 */
function action(projetId: string, reachedIndex: number): { label: string; to: string } {
  const aides = ROUTES.PROJET_DETAIL(projetId);
  const dossiers = `${aides}?tab=dossiers`;
  switch (reachedIndex) {
    case 0:
      return { label: 'Créer mon dossier', to: aides };
    case 1:
      return { label: 'Continuer mon dossier', to: dossiers };
    case 2:
      return { label: 'Suivre mon dépôt', to: dossiers };
    default:
      return { label: 'Estimer mes aides', to: aides };
  }
}

/**
 * Un projet dans l'onglet « Projets » d'un monument (maquette
 * `monumia-page-monument.html`) : son titre et son étape, les trois étapes en
 * grand, puis la bande bleue avec le nombre d'aides repérées et les deux
 * boutons. L'échéance ne s'y montre que si elle presse. Toute la carte mène
 * où mène le bouton orange (`.proj-lien::after`) ; « Voir les aides » passe
 * au-dessus.
 */
export function ProjetCard({ projet, monumentNom, stats, stage }: ProjetCardProps) {
  const etape = stage ?? projectStage(null, [], []);
  const { rang, action: quoi } = libelleEtape(etape);
  const cta = action(projet.id, etape.reachedIndex);
  const cloture = !!projet.clotureAt;
  const connu = montantTileMode(stats) !== 'nudge' && !!stats;
  const aides = stats?.aidesIdentifiees ?? 0;

  const prochaine = stats?.prochaineEcheance ?? null;
  const echeance = prochaine ? deadlineLabel(prochaine.date) : null;
  const presse = echeance && echeance.urgency !== 'normal';

  return (
    <article className={cloture ? 'proj clos' : 'proj'}>
      <div className="proj-top">
        <div>
          <h3>{projetTitre(projet, monumentNom)}</h3>
          <p className="st">
            {rang} : <b>{quoi}</b>
          </p>
        </div>
        {(cloture || presse) && (
          <div className="marques">
            {presse && echeance && (
              <span className={echeance.urgency === 'past' ? 'marque retard' : 'marque urgent'}>
                {echeance.urgency === 'past' ? 'Échéance dépassée' : `Échéance : ${echeance.text.toLowerCase()}`}
              </span>
            )}
            {cloture && <span className="marque">Clôturé</span>}
          </div>
        )}
      </div>
      <Avancement stage={etape} grand />
      <div className="proj-foot">
        <div className="num">
          {connu ? (
            <>
              <b>
                {aides} aide{aides > 1 ? 's' : ''}
              </b>
              <span>repérée{aides > 1 ? 's' : ''} pour ce projet</span>
            </>
          ) : (
            <>
              <b>Vos aides</b>
              <span>se découvrent en quelques questions</span>
            </>
          )}
        </div>
        <div className="act">
          {connu && (
            <Link className="btn b-ghost" to={ROUTES.PROJET_DETAIL(projet.id)}>
              Voir les aides
            </Link>
          )}
          <Link className="btn b-orange proj-lien" to={cta.to}>
            {cta.label}
            <Picto nom="fleche" />
          </Link>
        </div>
      </div>
    </article>
  );
}

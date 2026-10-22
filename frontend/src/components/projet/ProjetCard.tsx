import { Trans, useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { Avancement } from '@/components/shared/ecrans/Avancement';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ROUTES } from '@/constants/routes';
import i18n from '@/i18n';
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
      return { label: i18n.t('aide:ProjetCard.actions.creer'), to: aides };
    case 1:
      return { label: i18n.t('aide:ProjetCard.actions.continuer'), to: dossiers };
    case 2:
      return { label: i18n.t('aide:ProjetCard.actions.suivre'), to: dossiers };
    default:
      return { label: i18n.t('aide:ProjetCard.actions.estimer'), to: aides };
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
  const { t } = useTranslation('aide');
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
            <Trans t={t} i18nKey="ProjetCard.etape" values={{ rang, quoi }} components={{ b: <b /> }} />
          </p>
        </div>
        {(cloture || presse) && (
          <div className="marques">
            {presse && echeance && (
              <span className={echeance.urgency === 'past' ? 'marque retard' : 'marque urgent'}>
                {echeance.urgency === 'past'
                  ? t('ProjetCard.echeanceDepassee')
                  : t('ProjetCard.echeance', { texte: echeance.text.toLowerCase() })}
              </span>
            )}
            {cloture && <span className="marque">{t('ProjetCard.cloture')}</span>}
          </div>
        )}
      </div>
      <Avancement stage={etape} grand />
      <div className="proj-foot">
        <div className="num">
          {connu ? (
            <Trans
              t={t}
              i18nKey="ProjetCard.aidesReperees"
              count={aides}
              components={{ b: <b />, span: <span /> }}
            />
          ) : (
            <Trans t={t} i18nKey="ProjetCard.vosAides" components={{ b: <b />, span: <span /> }} />
          )}
        </div>
        <div className="act">
          {connu && (
            <Link className="btn b-ghost" to={ROUTES.PROJET_DETAIL(projet.id)}>
              {t('ProjetCard.voirAides')}
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

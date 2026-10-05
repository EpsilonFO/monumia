import { useNavigate } from 'react-router';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ROUTES } from '@/constants/routes';
import { questionsPourAide } from '@/lib/diagnostic-bilan';
import { financeurAide, guichet, montantAide, titreAide, type Guichet } from '@/lib/fiche-aide';
import { getEligibilityStatus, STATUS_PILL_LABEL, type EligibilityStatus } from './eligibility-status';
import type { AideMatchResult, ProjectQuestionnaireAnswers, QcmQuestion } from '@/types';

/** Pastille de droite, dans la bande bleue du pied de carte. */
const TON_PASTILLE: Record<EligibilityStatus, string> = {
  eligible: 'ok',
  potential: 'ck',
  atteignable: 'db',
  'non-eligible': 'no',
};

/** Étiquette du guichet, dans les trois couleurs de la maquette : vert quand on
 *  peut déposer sans échéance, orange quand une date limite court, sable pour
 *  tout ce qui n'est pas daté ou pas ouvert. */
function tonGuichet(aide: AideMatchResult['aide'], g: Guichet): 'o' | 'u' | 'd' {
  if (g.etat !== 'ouvert') return 'd';
  return !aide.permanent && aide.dateLimite ? 'u' : 'o';
}

interface AideCarteProps {
  match: AideMatchResult;
  /** Le PROJET dans lequel l'aide est vue : c'est lui qui clé la fiche d'aide. */
  projetId: string;
  /**
   * Le montant au pied de la carte. Retiré en offre gratuite : il reste lisible
   * sur la fiche de l'aide, mais mis sur chaque carte il promet un plan de
   * financement que l'offre ne suit pas encore.
   */
  showMontant?: boolean;
  /** De quoi compter les questions qui séparent encore l'aide d'un verdict.
   *  Elles se posent sur la fiche, jamais sur la carte. */
  questions?: QcmQuestion[];
  answers?: ProjectQuestionnaireAnswers;
}

/**
 * Carte d'une aide dans le diagnostic d'un projet (maquette
 * `monumia-page-aides.html`) : financeur et guichet, titre, le nombre de
 * questions qui restent (rien d'autre sous le titre : chapeau et motif
 * d'écart se lisent sur la fiche), puis la bande bleue du pied avec le montant et
 * l'éligibilité. Une aide qu'une seule question départage a son lien en
 * pastille orange : c'est la plus proche d'un verdict.
 *
 * La carte entière mène à la fiche, où se posent les questions qui restent :
 * la carte n'en donne que le nombre.
 */
export function AideCarte({ match, projetId, showMontant = true, questions, answers }: AideCarteProps) {
  const { aide } = match;
  const navigate = useNavigate();
  const statut = getEligibilityStatus(match);
  const g = guichet(aide);
  const montant = montantAide(aide);
  const ouvrir = () => navigate(ROUTES.PROJET_AIDE(projetId, aide.id));

  const restantes =
    questions && statut === 'potential' ? questionsPourAide(aide.id, questions, answers ?? {}).length : 0;
  const classes = ['card', statut === 'non-eligible' ? 'no' : '', restantes === 1 ? 'q1' : ''].filter(Boolean);

  return (
    <article
      className={classes.join(' ')}
      role="link"
      tabIndex={0}
      onClick={ouvrir}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          ouvrir();
        }
      }}
    >
      <div className="c-tags">
        <span className="c-tag f" title={financeurAide(aide)}>
          {financeurAide(aide)}
        </span>
        <span className={`c-tag ${tonGuichet(aide, g)}`}>
          <i className="dot" />
          {g.libelle}
        </span>
      </div>
      <h4>{titreAide(aide)}</h4>
      {restantes > 0 && (
        <span className="q-l">
          {restantes === 1 ? '1 question pour trancher' : `${restantes} questions pour trancher`}
          <Picto nom="fleche" />
        </span>
      )}
      <div className="c-foot">
        <span className="amt">
          <span className="ic">
            <Picto nom="euro" />
          </span>
          {!showMontant ? (
            <b className="none">Montant sur la fiche</b>
          ) : montant ? (
            <b>{montant.valeur}</b>
          ) : (
            <b className="none">Montant non publié</b>
          )}
        </span>
        <span className={`st ${TON_PASTILLE[statut]}`}>
          <i className="dot" />
          {STATUS_PILL_LABEL[statut]}
        </span>
      </div>
    </article>
  );
}

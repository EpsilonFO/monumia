import { useNavigate } from 'react-router';
import { Ico } from '@/components/aide/fiche/Ico';
import { ROUTES } from '@/constants/routes';
import { questionsPourAide } from '@/lib/diagnostic-bilan';
import { CLASSE_GUICHET, chapeauAide, financeurAide, guichet, montantAide, titreAide } from '@/lib/fiche-aide';
import { getEligibilityStatus, STATUS_PILL_LABEL, type EligibilityStatus } from './eligibility-status';
import type { AideMatchResult, ProjectQuestionnaireAnswers, QcmQuestion } from '@/types';

const TON_PASTILLE: Record<EligibilityStatus, string> = {
  eligible: 'ok',
  potential: '',
  atteignable: 'info',
  'non-eligible': 'no',
};

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
 * Carte d'une aide dans le diagnostic d'un projet, dessinée comme l'index des
 * fiches de la maquette : financeur et guichet, titre, chapeau, montant. La
 * maquette n'avait pas d'éligibilité, qui est ici la raison d'être de la liste :
 * elle prend la pastille de droite du pied de carte.
 *
 * La carte entière mène à la fiche, où se posent les questions qui restent :
 * la carte n'en donne que le nombre.
 */
export function AideCarte({ match, projetId, showMontant = true, questions, answers }: AideCarteProps) {
  const { aide } = match;
  const navigate = useNavigate();
  const statut = getEligibilityStatus(match);
  const g = guichet(aide);
  const montant = showMontant ? montantAide(aide) : null;
  const ouvrir = () => navigate(ROUTES.PROJET_AIDE(projetId, aide.id));

  const restantes =
    questions && statut === 'potential' ? questionsPourAide(aide.id, questions, answers ?? {}).length : 0;
  const raison = statut === 'non-eligible' ? match.criteresNonRemplis[0] : undefined;

  return (
    <div
      className="acard"
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
      <span className="tags">
        <b className="tag-fin" title={financeurAide(aide)}>{financeurAide(aide)}</b>
        <span className={`status ${CLASSE_GUICHET[g.etat]}`}><i />{g.libelle}</span>
      </span>
      <h3 title={titreAide(aide)}>{titreAide(aide)}</h3>
      <p>{chapeauAide(aide)}</p>
      {/* Ligne réservée, remplie ou non : les questions (ou le motif d'une aide
          écartée) tombent au même endroit sur toutes les cartes. */}
      <span className="acard-l">
        {raison ? (
          <span className="raison" title={raison}>{raison}</span>
        ) : restantes > 0 ? (
          <span className="plus">
            {restantes} question{restantes > 1 ? 's' : ''} pour trancher<Ico nom="fleche" />
          </span>
        ) : null}
      </span>
      <span className="acard-f">
        {montant ? <span className="amt"><Ico nom="montant" />{montant.valeur}</span> : <span />}
        <span className={`pill ${TON_PASTILLE[statut]}`}><i />{STATUS_PILL_LABEL[statut]}</span>
      </span>
    </div>
  );
}

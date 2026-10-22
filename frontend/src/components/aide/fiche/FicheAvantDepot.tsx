import { useTranslation } from 'react-i18next';
import { TexteAide } from '@/components/shared/TexteAide';
import { Ico } from './Ico';
import { Repli } from './Repli';
import type { PointReglement } from '@/lib/fiche-aide';
import type { AideLevier } from '@/types';

/** Le plan d'action d'un levier : ce qu'il faut faire, auprès de qui, en combien de temps. */
export function PlanLevier({ levier, titre = levier.resume }: { levier: AideLevier; titre?: string }) {
  const { t } = useTranslation('aide');
  return (
    <div className="levier">
      <b>{titre}</b>
      {levier.ecart && <p>{levier.ecart}</p>}
      {/* Paragraphes et puces, comme le `help` d'une question (cf. facts.yaml). */}
      {levier.demarche && <TexteAide className="demarche" texte={levier.demarche} />}
      {(levier.organisme || levier.cout || levier.delai) && (
        <dl>
          {levier.organisme && <div><dt>{t('levier.aupresDe')}</dt><dd>{levier.organisme}</dd></div>}
          {levier.cout && <div><dt>{t('levier.cout')}</dt><dd>{levier.cout}</dd></div>}
          {levier.delai && <div><dt>{t('levier.delai')}</dt><dd>{levier.delai}</dd></div>}
        </dl>
      )}
      {levier.url && (
        <a className="plink" href={levier.url} target="_blank" rel="noopener noreferrer">
          {t('levier.ouvrirDemarche')}<Ico nom="fleche" />
        </a>
      )}
    </div>
  );
}

/**
 * « Avant de déposer » : les démarches du règlement, juste sous le verdict.
 * Le questionnaire ne les pose pas, si bien qu'un « Vous remplissez ces
 * conditions » sans elles laisserait croire le dossier prêt. Le plan d'action
 * vient du diagnostic (`evaluation.demarche`) quand le fait cité en porte un.
 *
 * Déplié par défaut, et repliable. C'est ici, et plus dans le règlement, que
 * vivent ces points : chacun porte son ancre (`p-<id>`) et son texte officiel.
 */
export function FicheAvantDepot({
  demarches,
  plans,
}: {
  demarches: PointReglement[];
  plans: Map<string, AideLevier>;
}) {
  const { t } = useTranslation('aide');
  if (!demarches.length) return null;
  const n = demarches.length;
  return (
    <Repli
      id="avant-depot"
      className="avant"
      classeEntete="avant-h"
      titre={t('FicheAvantDepot.titre')}
      ouvertParDefaut
      entete={
        <>
          <span className="chip t-solid-orange"><Ico nom="delai" /></span>
          <div>
            <h2>{t('FicheAvantDepot.titre')}</h2>
            <p>{t('FicheAvantDepot.sousTitre', { count: n })}</p>
          </div>
        </>
      }
    >
      <ul>
        {demarches.map((p) => {
          const plan = plans.get(p.id);
          return (
            <li key={p.id} id={`p-${p.id}`}>
              <b>
                <span className="pn">{p.n}</span>
                {p.titre}
              </b>
              <p>{p.resume}</p>
              {p.derogation && <p className="derog">{t('FicheAvantDepot.derogation')}</p>}
              {plan && <PlanLevier levier={plan} titre={t('FicheAvantDepot.commentFaire')} />}
              {p.quote && (
                <details className="cite">
                  <summary>{t('FicheAvantDepot.texteOfficiel')}</summary>
                  <blockquote>{t('FicheAvantDepot.citation', { citation: p.quote })}</blockquote>
                </details>
              )}
            </li>
          );
        })}
      </ul>
    </Repli>
  );
}

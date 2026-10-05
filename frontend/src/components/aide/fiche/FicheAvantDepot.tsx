import { Ico } from './Ico';
import { Repli } from './Repli';
import type { PointReglement } from '@/lib/fiche-aide';
import type { AideLevier } from '@/types';

/** Le plan d'action d'un levier : ce qu'il faut faire, auprès de qui, en combien de temps. */
export function PlanLevier({ levier, titre = levier.resume }: { levier: AideLevier; titre?: string }) {
  return (
    <div className="levier">
      <b>{titre}</b>
      {levier.ecart && <p>{levier.ecart}</p>}
      {levier.demarche && <p>{levier.demarche}</p>}
      {(levier.organisme || levier.cout || levier.delai) && (
        <dl>
          {levier.organisme && <div><dt>Auprès de</dt><dd>{levier.organisme}</dd></div>}
          {levier.cout && <div><dt>Coût</dt><dd>{levier.cout}</dd></div>}
          {levier.delai && <div><dt>Délai</dt><dd>{levier.delai}</dd></div>}
        </dl>
      )}
      {levier.url && (
        <a className="plink" href={levier.url} target="_blank" rel="noopener noreferrer">
          Ouvrir la démarche<Ico nom="fleche" />
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
  if (!demarches.length) return null;
  const n = demarches.length;
  return (
    <Repli
      id="avant-depot"
      className="avant"
      classeEntete="avant-h"
      titre="Avant de déposer"
      ouvertParDefaut
      entete={
        <>
          <span className="chip t-solid-orange"><Ico nom="delai" /></span>
          <div>
            <h2>Avant de déposer</h2>
            <p>
              {n === 1
                ? "Un point que le questionnaire ne vérifie pas. S'il manque, le dossier est refusé."
                : `${n} points que le questionnaire ne vérifie pas. S'il en manque un, le dossier est refusé.`}
            </p>
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
              {p.derogation && <p className="derog">Une dérogation est possible.</p>}
              {plan && <PlanLevier levier={plan} titre="Comment faire" />}
              {p.quote && (
                <details className="cite">
                  <summary>Texte officiel</summary>
                  <blockquote>« {p.quote} »</blockquote>
                </details>
              )}
            </li>
          );
        })}
      </ul>
    </Repli>
  );
}

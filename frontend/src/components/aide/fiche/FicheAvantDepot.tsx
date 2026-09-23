import { Ico } from './Ico';
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
 */
export function FicheAvantDepot({
  demarches,
  plans,
  onOuvrirPoint,
}: {
  demarches: PointReglement[];
  plans: Map<string, AideLevier>;
  onOuvrirPoint: (id: string) => void;
}) {
  if (!demarches.length) return null;
  const n = demarches.length;
  return (
    <section className="avant" aria-labelledby="avant-t">
      <div className="avant-h">
        <span className="chip t-solid-orange"><Ico nom="delai" /></span>
        <div>
          <h2 id="avant-t">Avant de déposer</h2>
          <p>
            {n === 1
              ? "Un point que le questionnaire ne vérifie pas. S'il manque, le dossier est refusé."
              : `${n} points que le questionnaire ne vérifie pas. S'il en manque un, le dossier est refusé.`}
          </p>
        </div>
      </div>
      <ul>
        {demarches.map((p) => {
          const plan = plans.get(p.id);
          return (
            <li key={p.id}>
              <b>{p.titre}</b>
              <p>{p.resume}</p>
              {plan && <PlanLevier levier={plan} titre="Comment faire" />}
              <button type="button" className="plink" onClick={() => onOuvrirPoint(p.id)}>
                Voir le point {p.n} du règlement<Ico nom="fleche" />
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

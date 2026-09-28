import { Ico } from './Ico';
import { Repli } from './Repli';
import type { AideFicheRedigee } from '@/types';

/**
 * « Nos conseils pour ce dossier ». Rédigés dans la fiche, jamais déduits : une
 * aide sans fiche n'en montre pas, plutôt que de paraphraser ses conditions.
 * Repliés par défaut : l'en-tête dit combien il y en a.
 */
export function FicheConseils({
  conseils,
  numeroDe,
  onOuvrirPoint,
}: {
  conseils: AideFicheRedigee['conseils'];
  numeroDe: (conditionId: string) => number | undefined;
  onOuvrirPoint: (conditionId: string) => void;
}) {
  if (!conseils.length) return null;
  return (
    <Repli
      className="tips"
      classeEntete="tips-h"
      titre="Nos conseils pour ce dossier"
      entete={
        <>
          <span className="chip t-solid-orange"><Ico nom="ampoule" /></span>
          <div>
            <h2>Nos conseils pour ce dossier</h2>
            <p>
              {conseils.length === 1 ? 'Un conseil' : `${conseils.length} conseils`} tirés du règlement du
              financeur
            </p>
          </div>
        </>
      }
    >
      <ol>
        {conseils.map((c, i) => {
          const n = c.condition ? numeroDe(c.condition) : undefined;
          return (
            <li key={i}>
              <div>
                <b>{c.titre}</b>
                <p>{c.texte}</p>
                {c.condition && n && (
                  <button type="button" className="plink" onClick={() => onOuvrirPoint(c.condition!)}>
                    Voir le point {n} du règlement<Ico nom="fleche" />
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </Repli>
  );
}

/** « Comment ça se passe » : les étapes rédigées, ou la démarche découpée. Repliée par défaut. */
export function FicheEtapes({ etapes }: { etapes: { titre: string; texte?: string | null }[] }) {
  if (!etapes.length) return null;
  return (
    <Repli
      className="repli-bloc"
      titre="Comment ça se passe"
      entete={
        <div className="block-head">
          <h2>Comment ça se passe</h2>
          <span className="meta">{etapes.length === 1 ? 'Une étape' : `${etapes.length} étapes`}</span>
        </div>
      }
    >
      <ol className="steps">
        {etapes.map((e, i) => (
          <li key={i}>
            <span className="n">{i + 1}</span>
            <div>
              {e.texte ? (
                <>
                  <b>{e.titre}</b>
                  <p>{e.texte}</p>
                </>
              ) : (
                <p className="seul">{e.titre}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </Repli>
  );
}

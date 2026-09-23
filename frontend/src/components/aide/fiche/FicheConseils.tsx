import { Ico } from './Ico';
import type { AideFicheRedigee } from '@/types';

/**
 * « Nos conseils pour ce dossier ». Rédigés dans la fiche, jamais déduits : une
 * aide sans fiche n'en montre pas, plutôt que de paraphraser ses conditions.
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
    <section className="tips" aria-labelledby="tips-t">
      <div className="tips-h">
        <span className="chip t-solid-orange"><Ico nom="ampoule" /></span>
        <div>
          <h2 id="tips-t">Nos conseils pour ce dossier</h2>
          <p>Tirés du règlement du financeur</p>
        </div>
      </div>
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
    </section>
  );
}

/** « Comment ça se passe » : les étapes rédigées, ou la démarche découpée. */
export function FicheEtapes({ etapes }: { etapes: { titre: string; texte?: string | null }[] }) {
  if (!etapes.length) return null;
  return (
    <>
      <div className="block-head"><h2>Comment ça se passe</h2></div>
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
    </>
  );
}

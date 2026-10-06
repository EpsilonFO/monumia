import type { HTMLAttributes } from 'react';
import { blocsTexteAide } from '@/lib/texte-aide';

/**
 * Le texte d'aide d'une question, en paragraphes et en puces (cf.
 * `blocsTexteAide`). Sans style propre : l'encadré qui l'accueille décide.
 */
export function TexteAide({
  texte,
  ...attributs
}: { texte: string } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div {...attributs}>
      {blocsTexteAide(texte).map((bloc, i) =>
        bloc.type === 'p' ? (
          <p key={i}>{bloc.texte}</p>
        ) : (
          <ul key={i}>
            {bloc.puces.map((puce, j) => (
              <li key={j}>{puce}</li>
            ))}
          </ul>
        ),
      )}
    </div>
  );
}

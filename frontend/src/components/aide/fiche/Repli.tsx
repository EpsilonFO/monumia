import { useEffect, useId, useState, type ReactNode } from 'react';
import { Ico } from './Ico';
import { EVENEMENT_OUVRIR } from './useFiche';

/**
 * Une section repliable de la fiche (dépliée ou non à l'arrivée, selon
 * `ouvertParDefaut`). L'en-tête garde son titre
 * (un vrai `h2`) et devient cliquable d'un bout à l'autre : le bouton au
 * chevron s'étend dessus (`.repli-b::after`). Le corps se déplie en douceur
 * (`grid-template-rows` de 0fr à 1fr), et reste `inert` replié : ni tabulation
 * ni lecteur d'écran n'y entrent.
 */
export function Repli({
  id,
  className,
  classeEntete,
  titre,
  entete,
  children,
  ouvertParDefaut = false,
}: {
  id?: string;
  className: string;
  /** Classe de plus sur l'en-tête (`avant-h`, `tips-h`), qui porte son style. */
  classeEntete?: string;
  /** Nom du bouton pour les lecteurs d'écran : « Afficher “Avant de déposer” ». */
  titre: string;
  /** Le contenu de l'en-tête (pastille, titre, sous-titre), rangé à gauche du chevron. */
  entete: ReactNode;
  children: ReactNode;
  ouvertParDefaut?: boolean;
}) {
  const [ouvert, setOuvert] = useState(ouvertParDefaut);
  const corps = useId();

  useEffect(() => {
    if (!id) return;
    const surOuverture = (e: Event) => {
      if ((e as CustomEvent<string>).detail === id) setOuvert(true);
    };
    window.addEventListener(EVENEMENT_OUVRIR, surOuverture);
    return () => window.removeEventListener(EVENEMENT_OUVRIR, surOuverture);
  }, [id]);

  return (
    <section className={`${className} repli${ouvert ? ' ouvert' : ''}`} id={id}>
      <div className={classeEntete ? `repli-h ${classeEntete}` : 'repli-h'}>
        {entete}
        <button
          type="button"
          className="repli-b"
          aria-expanded={ouvert}
          aria-controls={corps}
          aria-label={ouvert ? `Replier « ${titre} »` : `Afficher « ${titre} »`}
          onClick={() => setOuvert((o) => !o)}
        >
          <Ico nom="chevron" />
        </button>
      </div>
      <div className="repli-corps" id={corps}>
        <div inert={!ouvert}>{children}</div>
      </div>
    </section>
  );
}

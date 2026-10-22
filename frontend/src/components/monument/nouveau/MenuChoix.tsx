import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Picto } from '@/components/shared/ecrans/Picto';
import { basculerChoix, libelleChoix, type GroupeChoix } from '@/lib/fiche-monument';

interface MenuChoixProps {
  /** Nom du champ, lu par les lecteurs d'écran devant la sélection. */
  label: string;
  placeholder: string;
  groupes: readonly GroupeChoix[];
  valeurs: readonly string[];
  onChange: (valeurs: string[]) => void;
  /** Plusieurs réponses (cases carrées, pied « Valider ») ou une seule (rondes). */
  multiple?: boolean;
  /** Champ « Rechercher » en tête de la liste. */
  recherche?: boolean;
  /** Réponses qui excluent les autres (cf. `basculerChoix`). */
  exclusifs?: readonly string[];
  /** Texte hors de la liste, montré tel quel en pastille claire. */
  texteLibre?: string;
  onEffacerTexteLibre?: () => void;
  /** Phrase en tête de la liste ouverte. */
  notePanel?: ReactNode;
}

const MAX_PASTILLES = 4;

/**
 * Le menu déroulant à choix de la maquette (`.ms`) : un bouton qui porte la
 * sélection en pastilles, une liste groupée qui s'ouvre dessous.
 */
export function MenuChoix({
  label,
  placeholder,
  groupes,
  valeurs,
  onChange,
  multiple = false,
  recherche = false,
  exclusifs = [],
  texteLibre,
  onEffacerTexteLibre,
  notePanel,
}: MenuChoixProps) {
  const { t } = useTranslation(['monuments', 'common']);
  const [ouvert, setOuvert] = useState(false);
  const [requete, setRequete] = useState('');
  const racine = useRef<HTMLDivElement>(null);
  const bouton = useRef<HTMLButtonElement>(null);
  const liste = useRef<HTMLDivElement>(null);

  const fermer = (rendreLeFocus = false) => {
    setOuvert(false);
    if (rendreLeFocus) bouton.current?.focus();
  };

  // Un clic hors du menu le referme ; Échap aussi, en rendant le focus au bouton.
  useEffect(() => {
    if (!ouvert) return;
    const auClic = (e: MouseEvent) => {
      if (!racine.current?.contains(e.target as Node)) setOuvert(false);
    };
    const auClavier = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOuvert(false);
        bouton.current?.focus();
      }
    };
    document.addEventListener('mousedown', auClic);
    document.addEventListener('keydown', auClavier);
    return () => {
      document.removeEventListener('mousedown', auClic);
      document.removeEventListener('keydown', auClavier);
    };
  }, [ouvert]);

  // À l'ouverture, le focus va au champ de recherche, sinon à la première réponse.
  useEffect(() => {
    if (!ouvert) return;
    const cible = liste.current?.querySelector<HTMLElement>('input, .o');
    cible?.focus();
  }, [ouvert]);

  const choisir = (v: string) => {
    if (!multiple) {
      onChange([v]);
      fermer(true);
      return;
    }
    onChange(basculerChoix(valeurs, v, exclusifs));
  };

  const q = requete.trim().toLowerCase();
  const groupesVisibles = groupes
    .map((g) => ({ ...g, options: g.options.filter((o) => !q || o.label.toLowerCase().includes(q)) }))
    .filter((g) => g.options.length > 0);

  const pastilles =
    valeurs.length > 0 ? (
      <>
        {valeurs.slice(0, MAX_PASTILLES).map((v) => (
          <span className="chip" key={v}>
            {libelleChoix(groupes, v)}
            <i
              aria-hidden="true"
              onClick={(e) => {
                e.stopPropagation();
                onChange(valeurs.filter((x) => x !== v));
              }}
            >
              ×
            </i>
          </span>
        ))}
        {valeurs.length > MAX_PASTILLES && (
          <span className="chip more">+{valeurs.length - MAX_PASTILLES}</span>
        )}
      </>
    ) : texteLibre ? (
      <span className="chip libre">
        {texteLibre}
        {onEffacerTexteLibre && (
          <i
            aria-hidden="true"
            onClick={(e) => {
              e.stopPropagation();
              onEffacerTexteLibre();
            }}
          >
            ×
          </i>
        )}
      </span>
    ) : (
      <span className="ph">{placeholder}</span>
    );

  return (
    <div
      className="ms"
      ref={racine}
      // Le focus qui quitte le menu (Tab vers le champ suivant) le referme,
      // comme un clic ailleurs.
      onBlur={(e) => {
        const vers = e.relatedTarget as Node | null;
        if (ouvert && vers && !racine.current?.contains(vers)) setOuvert(false);
      }}
    >
      <button
        ref={bouton}
        type="button"
        className="ms-btn"
        aria-haspopup="true"
        aria-expanded={ouvert}
        onClick={() => {
          setRequete('');
          setOuvert((o) => !o);
        }}
      >
        <span className="sr">{t('MenuChoix.libelleLecteur', { label })}</span>
        {pastilles}
      </button>

      {ouvert && (
        <div className="panel" role="menu" aria-label={label} ref={liste}>
          {recherche && (
            <div className="srch">
              <input
                type="search"
                placeholder={t('common:actions.rechercher')}
                aria-label={t('MenuChoix.rechercherAria')}
                value={requete}
                onChange={(e) => setRequete(e.target.value)}
              />
            </div>
          )}
          {notePanel && <p className="pnote">{notePanel}</p>}
          <div className="opts">
            {groupesVisibles.length === 0 ? (
              <p className="none">{t('MenuChoix.aucunResultat')}</p>
            ) : (
              groupesVisibles.map((g) => (
                <div key={g.titre || '_'}>
                  {g.titre && <div className="grp">{g.titre}</div>}
                  {g.options.map((o) => (
                    <button
                      key={o.value}
                      type="button"
                      className={multiple ? 'o' : 'o single'}
                      role={multiple ? 'menuitemcheckbox' : 'menuitemradio'}
                      aria-checked={valeurs.includes(o.value)}
                      onClick={() => choisir(o.value)}
                    >
                      <span className="bx">
                        <Picto nom="coche" className="" />
                      </span>
                      <span>
                        {o.label}
                        {o.hint && <small>{o.hint}</small>}
                      </span>
                    </button>
                  ))}
                </div>
              ))
            )}
          </div>
          {multiple && (
            <div className="panel-f">
              <span>
                {valeurs.length
                  ? t('MenuChoix.choisis', { count: valeurs.length })
                  : t('MenuChoix.aucunChoix')}
              </span>
              <button type="button" onClick={() => fermer(true)}>
                {t('common:actions.valider')}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

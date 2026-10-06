import { Children, useId, useState, type KeyboardEvent, type ReactNode, type Ref } from 'react';
import { Loader2 } from 'lucide-react';
import { Picto } from '@/components/shared/ecrans/Picto';
import { TexteAide } from '@/components/shared/TexteAide';
import { classeColonnes } from '@/lib/question-reponse';
import { longueurTexteAide } from '@/lib/texte-aide';
import { cn } from '@/lib/utils';

/**
 * Au-delà, le « Bon à savoir » est replié à trois lignes. Seuil calé sur la
 * largeur de lecture (62ch) : les textes courts s'affichent en entier, les
 * longs (la moitié de l'ontologie dépasse 190 caractères) ne poussent pas les
 * réponses sous la ligne de flottaison. Même seuil que `QuestionHelp`, qui sert
 * la fiche d'une aide.
 */
const POURQUOI_REPLIE = 170;

/** Au-delà, le titre de la question perd une taille : il tient sur l'écran. */
const TITRE_LONG = 120;

/**
 * L'encart bleu « Bon à savoir », avec son rond « i » : pourquoi on pose la
 * question, ou ce que veulent dire ses termes. Le texte garde ses paragraphes
 * et ses puces (`TexteAide`).
 */
function Pourquoi({ texte }: { texte: string }) {
  const [ouvert, setOuvert] = useState(false);
  const long = longueurTexteAide(texte) > POURQUOI_REPLIE;
  return (
    <div className="why">
      <span className="ic" aria-hidden="true">
        i
      </span>
      <div>
        <b>Bon à savoir</b>
        <TexteAide texte={texte} className={cn('corps', long && !ouvert && 'replie')} />
        {long && (
          <button type="button" onClick={() => setOuvert((o) => !o)} aria-expanded={ouvert}>
            {ouvert ? 'Réduire' : 'Lire la suite'}
          </button>
        )}
      </div>
    </div>
  );
}

interface CarteReponseProps {
  label: string;
  /** La précision sous le libellé, quand il y en a une. */
  description?: string | null;
  selected: boolean;
  /** Choix multiple : case carrée plutôt que rond. */
  multiple?: boolean;
  /** Réponse « je ne sais pas » du moteur : libellé moins appuyé. */
  nsp?: boolean;
  /** Réponse à part, sur toute la largeur de la grille. */
  large?: boolean;
  onSelect: () => void;
  /** Roving tabindex du questionnaire ; absent, la carte est tabulable. */
  tabIndex?: number;
  onKeyDown?: (e: KeyboardEvent<HTMLButtonElement>) => void;
  buttonRef?: Ref<HTMLButtonElement>;
}

/**
 * Une réponse, en carte : le rond (ou le carré) à cocher, le libellé en gras
 * (court : 45 caractères au plus), et la description facultative dessous, plus
 * petite et coupée à deux lignes. Elle se déplie en entier quand la carte est
 * cochée ou atteinte au clavier, et le survol la montre en infobulle : un
 * bouton « Lire la suite » DANS le bouton de la carte serait un contrôle
 * imbriqué. Cochée, la carte passe au bleu.
 */
export function CarteReponse({
  label,
  description,
  selected,
  multiple,
  nsp,
  large,
  onSelect,
  tabIndex,
  onKeyDown,
  buttonRef,
}: CarteReponseProps) {
  return (
    <button
      ref={buttonRef}
      type="button"
      className={cn('opt', multiple && 'multi', nsp && 'nsp', large && 'large')}
      role={multiple ? 'checkbox' : 'radio'}
      aria-checked={selected}
      tabIndex={tabIndex}
      onClick={onSelect}
      onKeyDown={onKeyDown}
    >
      <span className="rd" aria-hidden="true">
        <Picto nom="coche" />
      </span>
      <span>
        <b>{label}</b>
        {description && <small title={description}>{description}</small>}
      </span>
    </button>
  );
}

interface EcranQuestionProps {
  /** Petite ligne bleue au-dessus de la question. Rien quand on n'a pas de
   *  rubrique vraie à donner. */
  rubrique?: ReactNode;
  titre: string;
  /** Sous le titre : « Plusieurs réponses possibles. », par exemple. */
  consigne?: string | null;
  /** Le texte de l'encart « Bon à savoir » (paragraphes et puces admis). */
  pourquoi?: string | null;
  /** Au-dessus de la rubrique (le rappel des réponses reprises). */
  enTete?: ReactNode;
  /** Entre l'encart et les réponses (la liste des réponses à reprendre). */
  avantReponses?: ReactNode;
  /** Les cartes de réponse : elles sont posées dans la grille à deux colonnes. */
  children: ReactNode;
  /** Après les réponses (l'encart d'une réponse écartante). */
  apresReponses?: ReactNode;
  multiple?: boolean;
  /** Longue liste de réponses sans description : cartes serrées. */
  serre?: boolean;
  /** Désactive la grille pendant un enregistrement. */
  gele?: boolean;
  onPrecedent?: () => void;
  /** « Je ne sais pas, passer » : le lien n'est rendu que s'il est fourni. */
  onPasser?: () => void;
  onContinuer: () => void;
  continuerDesactive?: boolean;
  /** Pourquoi « Continuer » est inerte, dit aux lecteurs d'écran. */
  continuerIndice?: string;
  enCours?: boolean;
  /** « Vous pourrez modifier vos réponses plus tard. », quand c'est vrai. */
  modifiablePlusTard?: boolean;
  /** Animation d'entrée (`q-in-fwd`, `q-in-back`, ou celle de la maquette). */
  className?: string;
  /** Référence du titre, pour y poser le focus à l'arrivée. */
  titreRef?: Ref<HTMLHeadingElement>;
}

interface BlocsReponsesProps {
  /** Les blocs, dans l'ordre ; `titre: null` pour le bloc sans intertitre. */
  blocs: { titre: string | null; cartes: ReactNode[] }[];
  /** Les échappatoires (« Pas encore décidé »), sous tous les blocs. */
  pied?: ReactNode[];
  serre?: boolean;
}

/**
 * Les cartes rangées sous leurs intertitres : une sous-grille par bloc, trois
 * colonnes au plus, puis le pied. À poser dans la grille d'`EcranQuestion`,
 * qui passe alors en simple colonne (`.opts:has(> .grp)`).
 */
export function BlocsReponses({ blocs, pied = [], serre }: BlocsReponsesProps) {
  return (
    <>
      {blocs.map((bloc, i) => (
        <BlocReponses key={bloc.titre ?? `bloc-${i}`} titre={bloc.titre} serre={serre}>
          {bloc.cartes}
        </BlocReponses>
      ))}
      {pied.length > 0 && <div className={cn('opts', 'pied', serre && 'serre')}>{pied}</div>}
    </>
  );
}

function BlocReponses({
  titre,
  serre,
  children,
}: {
  titre: string | null;
  serre?: boolean;
  children: ReactNode[];
}) {
  const titreId = useId();
  return (
    <div className="grp" role="group" aria-labelledby={titre ? titreId : undefined}>
      {titre && (
        <p className="grp-t" id={titreId}>
          {titre}
        </p>
      )}
      <div className={cn('opts', classeColonnes(children.length, 3), serre && 'serre')}>
        {children}
      </div>
    </div>
  );
}

/**
 * Une question du wizard, au dessin de la maquette : rubrique, question en
 * sérif, consigne, encart « Bon à savoir », réponses en cartes sur deux colonnes,
 * puis la barre « Question précédente » / « Je ne sais pas, passer » /
 * « Continuer ». Les étapes de cadrage et le questionnaire du moteur la
 * partagent : le parcours se lit d'un bout à l'autre comme une seule suite.
 */
export function EcranQuestion({
  rubrique,
  titre,
  consigne,
  pourquoi,
  enTete,
  avantReponses,
  children,
  apresReponses,
  multiple,
  serre,
  gele,
  onPrecedent,
  onPasser,
  onContinuer,
  continuerDesactive,
  continuerIndice,
  enCours,
  modifiablePlusTard,
  className = 'entre',
  titreRef,
}: EcranQuestionProps) {
  const titreId = useId();
  const indiceId = useId();
  return (
    <>
      <section className={cn('q', className)} aria-labelledby={titreId}>
        {enTete}
        {rubrique && <span className="theme">{rubrique}</span>}
        {/* Les traits d'union de « comporte-t-il » ne coupent pas la ligne. */}
        <h1
          id={titreId}
          ref={titreRef}
          tabIndex={titreRef ? -1 : undefined}
          className={cn(titre.length > TITRE_LONG && 'long')}
        >
          {titre.replace(/-(t|il|elle|ils|elles|on|vous|nous)\b/g, '‑$1')}
        </h1>
        {consigne && <p className="hint">{consigne}</p>}
        {pourquoi && <Pourquoi texte={pourquoi} />}
        {avantReponses}
        <div
          className={cn('opts', classeColonnes(Children.count(children)), serre && 'serre')}
          role={multiple ? 'group' : 'radiogroup'}
          aria-labelledby={titreId}
          aria-disabled={gele || undefined}
          inert={gele || undefined}
        >
          {children}
        </div>
        {/* Annoncé poliment : l'encart arrive après le clic, et le lecteur
            d'écran doit l'entendre sans perdre le focus de la réponse. */}
        <div aria-live="polite">{apresReponses}</div>

        <div className="qz-nav">
          {onPrecedent && (
            <button className="btn b-line" type="button" onClick={onPrecedent} disabled={enCours}>
              <Picto nom="retour" />
              Question précédente
            </button>
          )}
          {onPasser && (
            <button className="skip" type="button" onClick={onPasser} disabled={enCours}>
              Je ne sais pas, passer
            </button>
          )}
          <button
            className="btn b-orange"
            type="button"
            onClick={onContinuer}
            disabled={continuerDesactive || enCours}
            aria-describedby={continuerDesactive && continuerIndice ? indiceId : undefined}
          >
            {enCours && <Loader2 className="spin" aria-hidden="true" />}
            Continuer
            {!enCours && <Picto nom="fleche" />}
          </button>
          {continuerIndice && (
            <span id={indiceId} className="sr">
              {continuerIndice}
            </span>
          )}
        </div>
      </section>
      {modifiablePlusTard && <p className="later">Vous pourrez modifier vos réponses plus tard.</p>}
    </>
  );
}

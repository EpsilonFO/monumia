import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';

interface PaywallContenu {
  /** Nom de l'offre qui ouvre ce que l'on montre : « Veille », « Multi-monuments ». */
  offre: string;
  /** Ce qui s'ouvre, en une phrase. C'est le titre de la carte. */
  titre: string;
  /** Deux ou trois lignes : ce qu'on y gagne, concrètement. */
  description: string;
  /**
   * Chiffres à mettre en avant. Ils portent l'enjeu réel du compte (un montant
   * d'aides, un nombre d'échéances) et c'est ce qui distingue une vraie porte
   * d'un argumentaire générique — d'où leur place DANS la carte, et non
   * derrière le flou où ils seraient illisibles.
   */
  chiffres?: { valeur: string; libelle: string }[];
  /** Monument d'où l'on part, pour que « Retour » revienne au bon endroit. */
  monumentId?: string;
}

/**
 * La carte de paywall : l'unique endroit où se rédige « voici ce que cette
 * offre ouvre ». Partagée par les deux formes ci-dessous.
 */
function PaywallCard({
  offre,
  titre,
  description,
  chiffres,
  monumentId,
  enModale = false,
}: PaywallContenu & {
  /**
   * En modale, le titre doit être un `DialogTitle` : c'est lui que Radix
   * annonce à l'ouverture, et son absence est une erreur d'accessibilité. En
   * place, c'est un titre ordinaire.
   */
  enModale?: boolean;
}) {
  const Titre = enModale ? DialogTitle : 'h2';
  return (
    <div
      className="w-full max-w-lg overflow-hidden rounded-2xl border-[1.5px] p-6 text-center"
      style={{ background: C.card, borderColor: C.orange, boxShadow: 'var(--shadow-pop)' }}
    >
      <span
        className="inline-flex items-center rounded-full px-2.5 py-1 text-[11.5px] font-bold uppercase tracking-[0.08em]"
        style={{ background: C.paleOrange, color: C.orange }}
      >
        {`Offre ${offre}`}
      </span>

      <Titre
        className="mt-3 block text-[19px] leading-snug"
        style={{ fontFamily: SERIF, color: C.ink }}
      >
        {titre}
      </Titre>

      <p className="mt-2 text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
        {description}
      </p>

      {chiffres && chiffres.length > 0 && (
        <div
          className="mt-5 grid gap-3 rounded-xl p-4"
          style={{
            background: C.paleBlue,
            gridTemplateColumns: `repeat(${chiffres.length}, minmax(0, 1fr))`,
          }}
        >
          {chiffres.map(({ valeur, libelle }) => (
            <div key={libelle} className="flex min-w-0 flex-col items-center gap-0.5">
              <span
                className="text-[17px] font-bold leading-tight tabular-nums"
                style={{ color: C.ink }}
              >
                {valeur}
              </span>
              <span className="text-[11px] leading-tight" style={{ color: C.grayMuted }}>
                {libelle}
              </span>
            </div>
          ))}
        </div>
      )}

      <Link
        to={ROUTES.TARIFS(monumentId)}
        className="group mt-5 inline-flex w-full items-center justify-center gap-2 rounded-full px-5 py-3 text-[14.5px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5"
        style={{ background: C.orange }}
      >
        {`Découvrir l'offre ${offre}`}
        <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
      </Link>
    </div>
  );
}

interface PaywallOverlayProps extends PaywallContenu {
  /** Le contenu réel, montré flouté derrière la carte. */
  children: ReactNode;
  /**
   * Hauteur maximale de l'APERÇU. Au-delà, il est coupé avec un dégradé : un
   * aperçu de deux écrans se parcourrait au défilement sans jamais devenir
   * lisible, et la carte s'en éloignerait. N'impose rien à la carte, qui peut
   * être plus haute que cette valeur — c'est elle qui fixe alors la hauteur.
   *
   * Le défaut vaut un plein écran, et ce n'est pas un chiffre en l'air : coupé
   * plus court, l'aperçu du tableau de bord ne montrait que l'en-tête et la
   * carte d'agenda, et pas une seule vignette de monument. Or ce sont elles
   * qu'on reconnaît.
   */
  hauteur?: string;
  /**
   * Intensité du flou. Le défaut est volontairement léger : deviner la forme
   * de ce qu'on n'a pas fait partie de l'argument.
   *
   * À monter là où l'aperçu porte un texte qu'on ne veut pas voir lu de loin —
   * les noms d'aides à venir. Ce n'est pas une protection pour autant : ces
   * noms partent en clair dans la réponse HTTP, et le seul contrôle qui tienne
   * est celui posé sur GET /aides/{id}.
   */
  flou?: string;
  /**
   * Faux : le contenu s'affiche net, sans carte, mais dans le MÊME arbre. C'est
   * ce qui permet à un garde de poser le paywall une fois l'offre connue sans
   * démonter la page derrière — la remonter relançait ses chargements et
   * remettait ses squelettes (cf. `DashboardRoute`). Défaut : vrai.
   */
  actif?: boolean;
}

/**
 * Paywall EN PLACE : le contenu réel derrière, flouté, avec la carte devant.
 *
 * Montrer plutôt que masquer, parce que ce qui est vendu ici est une VUE sur
 * les données du compte — son tableau de bord, son équipe, ses échéances. Il
 * n'y a donc rien à cacher : l'aperçu flou dit « ceci existe et vous concerne »
 * là où une page vide ne dit rien.
 *
 * Ce raisonnement ne vaut QUE pour les données du compte lui-même. Pour du
 * contenu payant — le nom d'une aide dont le guichet n'est pas ouvert — le flou
 * CSS ne protège rien : le texte part quand même dans la réponse HTTP. Ces
 * contenus-là sont caviardés côté serveur AVANT d'arriver ici (cf.
 * `redact_bientot_hors_offre`), et le flou n'est que leur habillage.
 */
export function PaywallOverlay({
  children,
  hauteur = 'min(82vh, 50rem)',
  flou = '2.5px',
  actif = true,
  ...contenu
}: PaywallOverlayProps) {
  if (!actif) {
    // Même structure que ci-dessous (grille > cellule > contenu), pour que
    // React garde l'instance des enfants quand le paywall s'active.
    return (
      <div className="grid">
        <div style={{ gridArea: '1 / 1' }}>{children}</div>
      </div>
    );
  }
  return (
    // Une seule cellule de grille, où l'aperçu et la carte se superposent : la
    // hauteur du bloc suit le PLUS GRAND des deux. Avec un calque en position
    // absolue, une carte plus haute que son aperçu — c'est le cas de
    // l'échéancier, court — débordait de son cadre.
    <div className="grid">
      <div
        // Le rognage et le flou portent sur le MÊME élément, et dans cet ordre :
        // le contenu est coupé, puis flouté. En les séparant, le navigateur
        // devait rasteriser toute la hauteur réelle du tableau de bord pour
        // n'en montrer qu'un écran, et le rendu s'y dégradait — images pâles ou
        // à moitié peintes.
        //
        // `inert` : ni cliquable, ni atteignable au clavier, ni lu par un
        // lecteur d'écran. Sans cela, la tabulation traverserait un contenu
        // illisible.
        inert
        aria-hidden
        className="pointer-events-none select-none overflow-hidden rounded-2xl"
        // Le flou passe par `filter` en style inline plutôt que par une classe
        // Tailwind : son intensité varie d'un appelant à l'autre, et une classe
        // arbitraire par valeur ne se génère pas depuis une variable.
        //
        // `center` : quand la carte est plus haute que l'aperçu, celui-ci se
        // place derrière elle plutôt que collé en haut de la cellule, ce qui
        // laisserait un vide sous le verre.
        style={{
          gridArea: '1 / 1',
          maxHeight: hauteur,
          alignSelf: 'center',
          filter: `blur(${flou})`,
        }}
      >
        {children}
      </div>

      <div
        className="relative flex items-center justify-center p-4"
        style={{ gridArea: '1 / 1' }}
      >
        {/* Voile translucide plutôt qu'un aperçu assombri : le contenu garde ses
            couleurs et sa netteté de photo, et c'est le verre qui adoucit. Un
            `opacity` sur l'aperçu lui-même donnait des images délavées, qu'on
            lisait comme un chargement inachevé.
            
            `opacity` sur un fond PLEIN, et non l'alpha de Tailwind (`/30`) :
            celui-ci compile en `color-mix`, précédé d'un repli opaque pour les
            navigateurs qui ne le connaissent pas. Là où le repli s'applique,
            le voile masque tout l'aperçu. */}
        <div
          aria-hidden
          className="absolute inset-0 rounded-2xl bg-app-bg"
          style={{ opacity: 0.3 }}
        />

        {/* Dégradé de coupe : l'aperçu est tronqué, autant que la limite soit
            assumée plutôt que nette. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-24 rounded-b-2xl"
          style={{ background: 'linear-gradient(to top, var(--app-bg), transparent)' }}
        />

        <div className="relative">
          <PaywallCard {...contenu} />
        </div>
      </div>
    </div>
  );
}

interface PaywallDialogProps extends PaywallContenu {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Paywall en MODALE : la page reste derrière, floutée par le voile.
 *
 * C'est la forme des ACTIONS — « Nouveau monument », « Nouveau projet ». Il n'y
 * a rien à montrer en aperçu d'un geste qu'on n'a pas encore fait, et une
 * modale garde le contexte : on referme et on est resté sur sa liste, là où une
 * redirection vers les tarifs aurait fait perdre sa place.
 */
export function PaywallDialog({ open, onOpenChange, ...contenu }: PaywallDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        overlayClassName="bg-black/25 backdrop-blur-[3px]"
        className="border-none bg-transparent p-0 shadow-none sm:max-w-lg"
        showCloseButton={false}
      >
        <DialogDescription className="sr-only">{contenu.description}</DialogDescription>
        <PaywallCard {...contenu} enModale />
      </DialogContent>
    </Dialog>
  );
}

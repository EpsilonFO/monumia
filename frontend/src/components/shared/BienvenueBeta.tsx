import { useCallback, useEffect, useState, type MouseEvent } from 'react';
import { createPortal } from 'react-dom';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { useAuthStore } from '@/stores/useAuthStore';
import { C, SERIF } from '@/lib/brand';
import { idProjetYbug } from '@/lib/ybug';
import {
  dejaAccueilli,
  marquerAccueilli,
  MARGE_HALO,
  positionBulle,
  type Cadre,
} from '@/lib/bienvenue-beta';

/** Posé par le script Ybug sur son bouton (cf. `index.css`). */
const ID_BOUTON_YBUG = '__ybug-launcher';

/**
 * Le script Ybug se charge en asynchrone : on lui laisse ce délai pour poser
 * son bouton. Au-delà, l'accueil s'arrête après la modale plutôt que de
 * projeter un halo sur le vide.
 */
const ATTENTE_BOUTON_MS = 10_000;

/**
 * Au-dessus du bouton Ybug, dont le z-index est celui de son script : le voile
 * doit le recouvrir pour attraper le clic, le halo le laissant voir au travers.
 */
const Z_PROJECTEUR = 2147483647;

type Etape = 'bienvenue' | 'bouton' | 'fini';

/**
 * Accueil des bêta-testeurs, une fois par compte : la modale de bienvenue, puis
 * un projecteur sur le bouton de retour en bas à droite.
 *
 * Monté dans `AppLayout`, et non à la racine : on n'interrompt ni les wizards
 * ni la connexion, et la première arrivée dans l'espace suit de toute façon
 * l'inscription.
 */
export function BienvenueBeta() {
  const userId = useAuthStore((s) => s.user?.id);
  // Décidé une fois, au montage : relu à chaque rendu, `dejaAccueilli`
  // passerait à vrai dès la sortie de la modale et couperait le projecteur.
  const [aAccueillir] = useState(() =>
    userId && idProjetYbug() && !dejaAccueilli(userId) ? userId : null
  );
  const [etape, setEtape] = useState<Etape>('bienvenue');

  // Marqué dès la sortie de la modale : quitter l'onglet pendant le projecteur
  // ne doit pas tout rejouer à la visite suivante.
  const versBouton = useCallback(() => {
    if (aAccueillir) marquerAccueilli(aAccueillir);
    setEtape('bouton');
  }, [aAccueillir]);
  const terminer = useCallback(() => {
    if (aAccueillir) marquerAccueilli(aAccueillir);
    setEtape('fini');
  }, [aAccueillir]);

  // `!== userId` : un changement de compte sans démontage n'hérite pas de
  // l'accueil décidé pour le précédent.
  if (!aAccueillir || aAccueillir !== userId || etape === 'fini') return null;

  if (etape === 'bienvenue') {
    return (
      <Dialog open onOpenChange={(ouvert) => !ouvert && versBouton()}>
        <DialogContent
          showCloseButton={false}
          className="gap-0 rounded-2xl border-[1.5px] p-8 sm:max-w-[34rem]"
          style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-pop)' }}
        >
          <p className="text-[15px] font-semibold" style={{ color: C.orange }}>
            Version bêta
          </p>
          <DialogTitle
            className="mt-2 text-[27px] leading-tight font-normal"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            Bienvenue sur Monumia
          </DialogTitle>
          <DialogDescription asChild>
            <div className="mt-4 space-y-3 text-[16.5px] leading-[1.7]" style={{ color: C.grayFg }}>
              <p>
                Merci d'avoir accepté de tester la plateforme. Monumia repère les aides auxquelles
                votre monument peut prétendre et vous accompagne dans le montage des dossiers.
              </p>
              <p>
                Elle est encore en rodage : un écran qui vous perd, une aide qui manque, un chiffre
                qui vous étonne, tout ce que vous remarquez en chemin nous aide à l'améliorer.
              </p>
            </div>
          </DialogDescription>
          <button
            type="button"
            onClick={versBouton}
            className="mt-7 w-full rounded-full px-5 py-3 text-[16.5px] font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
            style={{ background: C.orange }}
          >
            C'est parti
          </button>
        </DialogContent>
      </Dialog>
    );
  }

  return <ProjecteurRetour onFin={terminer} />;
}

/**
 * Le halo sur le bouton Ybug et sa bulle. Le cadre du bouton est relu à chaque
 * image : il bouge au redimensionnement, et sur téléphone `index.css` le
 * remonte au-dessus de la barre d'onglets.
 */
function ProjecteurRetour({ onFin }: { onFin: () => void }) {
  const [cadre, setCadre] = useState<Cadre | null>(null);

  useEffect(() => {
    const debut = performance.now();
    let image = 0;
    const suivre = () => {
      const bouton = document.getElementById(ID_BOUTON_YBUG);
      const r = bouton?.getBoundingClientRect();
      if (r && r.width > 0) {
        setCadre((avant) =>
          avant &&
          avant.top === r.top &&
          avant.left === r.left &&
          avant.width === r.width &&
          avant.height === r.height
            ? avant
            : { top: r.top, left: r.left, width: r.width, height: r.height }
        );
      } else if (performance.now() - debut > ATTENTE_BOUTON_MS) {
        onFin();
        return;
      }
      image = requestAnimationFrame(suivre);
    };
    image = requestAnimationFrame(suivre);
    return () => cancelAnimationFrame(image);
  }, [onFin]);

  useEffect(() => {
    const surTouche = (e: KeyboardEvent) => e.key === 'Escape' && onFin();
    window.addEventListener('keydown', surTouche);
    return () => window.removeEventListener('keydown', surTouche);
  }, [onFin]);

  if (!cadre) return null;

  const bulle = positionBulle(cadre, { largeur: window.innerWidth, hauteur: window.innerHeight });

  // Le voile couvre tout, bouton compris : un clic DANS le halo ouvre Ybug, un
  // clic ailleurs referme simplement l'accueil.
  const surClic = (e: MouseEvent) => {
    const dansHalo =
      e.clientX >= cadre.left - MARGE_HALO &&
      e.clientX <= cadre.left + cadre.width + MARGE_HALO &&
      e.clientY >= cadre.top - MARGE_HALO &&
      e.clientY <= cadre.top + cadre.height + MARGE_HALO;
    onFin();
    if (dansHalo) window.Ybug?.open?.();
  };

  return createPortal(
    <div
      className="fixed inset-0 animate-in fade-in-0 duration-300"
      style={{ zIndex: Z_PROJECTEUR }}
      onClick={surClic}
    >
      {/* Le halo : un trou dans le voile, découpé par l'ombre portée. */}
      <div
        aria-hidden
        className="pointer-events-none absolute rounded-full"
        style={{
          top: cadre.top - MARGE_HALO,
          left: cadre.left - MARGE_HALO,
          width: cadre.width + 2 * MARGE_HALO,
          height: cadre.height + 2 * MARGE_HALO,
          boxShadow: '0 0 0 9999px rgba(7, 20, 52, 0.62)',
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute animate-ping rounded-full border-2 motion-reduce:animate-none"
        style={{
          top: cadre.top - MARGE_HALO,
          left: cadre.left - MARGE_HALO,
          width: cadre.width + 2 * MARGE_HALO,
          height: cadre.height + 2 * MARGE_HALO,
          borderColor: C.orange,
          animationDuration: '1.8s',
        }}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="bienvenue-beta-retour"
        className="absolute rounded-2xl p-5 animate-in fade-in-0 slide-in-from-bottom-2 duration-300"
        style={{
          left: bulle.left,
          bottom: bulle.bottom,
          width: bulle.largeur,
          background: C.card,
          boxShadow: 'var(--shadow-pop)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="bienvenue-beta-retour"
          className="text-[20px] leading-snug"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          Un bug, une idée, une question ?
        </h2>
        <p className="mt-2 text-[15.5px] leading-[1.65]" style={{ color: C.grayFg }}>
          Écrivez-nous avec ce bouton, depuis n'importe quelle page. Vous pouvez capturer l'écran et
          l'annoter : on reçoit votre message avec la page où vous étiez.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onFin}
            className="rounded-full px-4 py-2 text-[15px] font-semibold"
            style={{ color: C.grayFg }}
          >
            Plus tard
          </button>
          <button
            type="button"
            autoFocus
            onClick={() => {
              onFin();
              window.Ybug?.open?.();
            }}
            className="rounded-full px-4 py-2 text-[15px] font-semibold text-white"
            style={{ background: C.orange }}
          >
            Essayer maintenant
          </button>
        </div>
        {/* La pointe, qui vise le centre du bouton. */}
        <span
          aria-hidden
          className="absolute -bottom-[7px] h-3.5 w-3.5 rotate-45"
          style={{ left: bulle.pointe - 7, background: C.card }}
        />
      </div>
    </div>,
    document.body
  );
}

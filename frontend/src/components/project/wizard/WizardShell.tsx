import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Picto } from '@/components/shared/ecrans/Picto';
import type { Monument } from '@/types';
import { WizardRail } from './WizardRail';
import type { WizardStep, WizardStepKey } from './etapes';
import '@/components/shared/ecrans/ecrans.css';
import './questionnaire.css';

/**
 * Ce que la colonne dit de l'enregistrement, en pied. `auFil` : les réponses
 * sont écrites à chaque geste (la coche verte n'est posée que dans ce cas) ;
 * sinon la phrase dit quand elles le seront.
 */
export interface NoteEnregistrement {
  texte: string;
  auFil: boolean;
}

interface WizardShellProps {
  /** Les étapes de CE wizard : le shell n'en connaît aucune en propre. */
  steps: WizardStep[];
  step: WizardStepKey;
  monument: Monument | null;
  /** Vrai quand quitter perdrait des réponses en cours → confirmation. */
  confirmQuit: boolean;
  /** Vrai sur un écran qui navigue de lui-même (le calcul du diagnostic) :
   *  une navigation concurrente arracherait l'utilisateur en plein vol. */
  quitDisabled?: boolean;
  /** Destination du bouton Quitter (le monument, sa liste, le projet…). */
  exitTo: string;
  /**
   * Remplace la navigation du bouton Quitter par une action de l'appelant.
   *
   * Sert au parcours découverte, où quitter le questionnaire ne doit pas faire
   * sortir : on va à l'écran de fin, qui montre ce que les réponses données ont
   * déjà trouvé. Abandonner en cours de route est le moment où l'on a le plus
   * à montrer, pas le moment de renvoyer sur une page de connexion.
   *
   * `exitTo` reste requis : la confirmation de sortie et les autres étapes
   * s'en servent toujours.
   */
  onQuit?: () => void;
  /** Texte de la confirmation de sortie, selon ce qui serait perdu. */
  quitMessage?: string;
  /**
   * Avancement du questionnaire (0 à 100), ou `null` hors du questionnaire.
   * Une barre et RIEN d'écrit : jamais de « Question N sur M » (cf.
   * `ProjectQuestionnaire`). La même valeur alimente la petite jauge sous
   * l'étape « Questionnaire » de la colonne.
   */
  progression?: number | null;
  /** Pied de colonne sur l'enregistrement, ou rien quand il n'y a rien de vrai à dire. */
  noteEnregistrement?: NoteEnregistrement | null;
  /**
   * Scène SANS les règles de base des écrans (`.ec`) : pour les étapes pas
   * encore portées sur la maquette (« Votre compte », l'attente du diagnostic,
   * les échecs de reprise), dont les utilitaires Tailwind seraient sinon
   * écrasés (`.ec a` repeint un bouton blanc en bleu, `.ec button` remet les
   * tailles de police à 16 px).
   */
  sceneLibre?: boolean;
  children: ReactNode;
}

/**
 * Coquille des wizards de projet, sur la maquette du designer : colonne de
 * 360 px à gauche (étapes, monument, enregistrement), zone de la question à
 * droite avec sa barre d'avancement et « Quitter ». Sous 980 px, la colonne se
 * replie sur le logo.
 *
 * La page ne défile jamais (hauteur de l'écran) : c'est la zone principale qui
 * porte le défilement, et on la remonte à chaque étape.
 */
export function WizardShell({
  steps,
  step,
  monument,
  confirmQuit,
  quitDisabled = false,
  exitTo,
  onQuit,
  quitMessage,
  progression = null,
  noteEnregistrement = null,
  sceneLibre = false,
  children,
}: WizardShellProps) {
  const navigate = useNavigate();
  const [quitOpen, setQuitOpen] = useState(false);
  const sceneRef = useRef<HTMLElement>(null);

  useEffect(() => {
    sceneRef.current?.scrollTo(0, 0);
  }, [step]);

  const quit = () => {
    if (quitDisabled) return;
    if (confirmQuit) setQuitOpen(true);
    else if (onQuit) onQuit();
    else navigate(exitTo);
  };

  // Un plancher visible : à la première question d'une longue liste, le ratio
  // réel ne ferait qu'un ou deux pixels, qu'on lirait comme une barre vide.
  // `aria-valuenow` garde la valeur exacte.
  const largeur = progression === null ? 0 : Math.max(progression, 3);

  return (
    <div className="qz">
      <WizardRail
        steps={steps}
        step={step}
        monument={monument}
        onQuit={quit}
        progression={progression === null ? null : largeur}
        noteEnregistrement={noteEnregistrement}
      />

      <main ref={sceneRef} className="qz-main">
        <div className="ec qz-top">
          {progression !== null && (
            <div
              className="qz-bar"
              role="progressbar"
              aria-label="Progression du questionnaire"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progression}
              aria-valuetext={`${progression}\u00a0% du questionnaire parcouru`}
            >
              <i style={{ width: `${largeur}%` }} />
            </div>
          )}
          {!quitDisabled && (
            <button className="qz-quit" type="button" onClick={quit}>
              <Picto nom="croix" />
              Quitter
            </button>
          )}
        </div>
        <div className={sceneLibre ? 'qz-scene' : 'ec qz-scene'}>{children}</div>
      </main>

      <AlertDialog open={quitOpen} onOpenChange={setQuitOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Quitter&nbsp;?</AlertDialogTitle>
            <AlertDialogDescription>
              {quitMessage ??
                'Vos réponses ne sont pas encore enregistrées : si vous quittez maintenant, vous devrez recommencer le questionnaire.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Continuer</AlertDialogCancel>
            <AlertDialogAction onClick={() => navigate(exitTo)}>Quitter</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

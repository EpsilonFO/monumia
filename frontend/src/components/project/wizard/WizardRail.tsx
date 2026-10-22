import { useTranslation } from 'react-i18next';
import { LogoMonumia } from '@/components/icons';
import { Picto } from '@/components/shared/ecrans/Picto';
import { PROTECTION_LABELS_SHORT } from '@/constants/monument-options';
import type { Monument } from '@/types';
import type { NoteEnregistrement } from './WizardShell';
import type { WizardStep, WizardStepKey } from './etapes';

interface WizardRailProps {
  steps: WizardStep[];
  step: WizardStepKey;
  monument: Monument | null;
  onQuit: () => void;
  /** Largeur de la jauge sous l'étape « Questionnaire », ou `null` pour ne pas
   *  la montrer. Une jauge seule, sans compteur (cf. `ProjectQuestionnaire`). */
  progression: number | null;
  noteEnregistrement: NoteEnregistrement | null;
}

/**
 * Colonne gauche du wizard, sur la maquette : le logo, les étapes (vertes et
 * cochées une fois faites, orange pour l'actuelle, reliées par un trait), la
 * carte du monument, et en pied ce qu'il advient des réponses. Sous 980 px,
 * seul le logo reste (cf. questionnaire.css). Aucun état propre.
 */
export function WizardRail({
  steps,
  step,
  monument,
  onQuit,
  progression,
  noteEnregistrement,
}: WizardRailProps) {
  // Les clés étant des chaînes, c'est le RANG dans la liste qui dit ce qui est
  // fait et ce qui reste.
  const { t } = useTranslation('project');
  const currentIndex = steps.findIndex((s) => s.key === step);

  return (
    <aside className="ec qz-side" aria-label={t('WizardRail.etapes')}>
      <button type="button" className="qz-logo" onClick={onQuit} aria-label={t('WizardRail.quitter')}>
        <LogoMonumia className="fleur" />
        <span className="nom">Monumia</span>
      </button>

      <ol className="qz-etapes">
        {steps.map((s, i) => {
          const state = i < currentIndex ? 'done' : i === currentIndex ? 'current' : 'upcoming';
          const done = state === 'done';
          const current = state === 'current';
          return (
            <li
              key={s.key}
              className={`qz-etape${done ? ' done' : current ? ' cur' : ''}`}
              aria-current={current ? 'step' : undefined}
            >
              <span className="qz-dot" aria-hidden="true">
                {done ? <Picto nom="coche" /> : i + 1}
              </span>
              <div>
                <b>
                  {s.label}
                  <span className="sr"> {t('WizardRail.etatEntreParentheses', { etat: t(`etatsEtape.${state}`) })}</span>
                </b>
                <small>{done ? t('WizardRail.termine') : s.hint}</small>
                {current && s.key === 'questionnaire' && progression !== null && (
                  <div className="qz-sub" aria-hidden="true">
                    <span className="track">
                      <i style={{ width: `${progression}%` }} />
                    </span>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {monument && (
        <div className="qz-mon">
          <span className="k">{t('WizardRail.votreMonument')}</span>
          <h3>{monument.nom}</h3>
          {monument.commune && <p>{monument.commune}</p>}
          <span className="tag">
            {PROTECTION_LABELS_SHORT[monument.protection] ?? monument.protection}
          </span>
        </div>
      )}

      {noteEnregistrement && (
        <p className="qz-save">
          {noteEnregistrement.auFil && (
            <svg
              className="i"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="m5 12.5 4.5 4.5L19 7.5" />
            </svg>
          )}
          {noteEnregistrement.texte}
        </p>
      )}
    </aside>
  );
}

import { PROJECT_STAGES, type ProjectStage } from '@/lib/project-stats';
import { rangEnCours } from '@/lib/avancement';
import { Picto } from './Picto';

/**
 * Les quatre étapes d'un projet (Estimation, Dossier, Dépôt, Suivi) : faites en
 * vert avec une coche, l'étape en cours en orange, les suivantes au trait.
 * `grand` : la version pleine largeur de la carte projet, avec « En cours »
 * sous l'étape actuelle.
 */
export function Avancement({ stage, grand = false }: { stage: ProjectStage; grand?: boolean }) {
  const enCours = rangEnCours(stage);
  return (
    <ol className={grand ? 'steps lg' : 'steps'} aria-label="Avancement du projet">
      {PROJECT_STAGES.map((s, i) => {
        const etat = i < enCours ? 'ok' : i === enCours ? 'cur' : undefined;
        return (
          <li key={s.key} className={etat} aria-current={etat === 'cur' ? 'step' : undefined}>
            <span className="n">{etat === 'ok' ? <Picto nom="coche" /> : i + 1}</span>
            {grand ? <b>{s.label}</b> : s.label}
            {grand && etat === 'cur' && <small>En cours</small>}
          </li>
        );
      })}
    </ol>
  );
}

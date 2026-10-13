import { useState } from 'react';
import { Link } from 'react-router';
import { format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Picto } from '@/components/shared/ecrans/Picto';
import { deadlineLink } from '@/lib/project-stats';
import type { ProjectDeadline } from '@/lib/project-stats';

/** Au-delà, les dates suivantes se déplient sous la grille. */
const VISIBLES = 4;
/** Une échéance à 45 jours ou moins passe en orange : c'est le temps qu'il faut
 *  pour réunir les pièces d'un dossier. */
const SEUIL_URGENT = 45;
/** Horizon de la jauge : une date à six mois ou plus laisse la jauge au plancher. */
const HORIZON = 180;

interface ProjectEcheancierProps {
  deadlines: ProjectDeadline[];
  /** Titre et montant écrits d'une aide, pour la carte de sa date limite. */
  aide?: (aideId: string) => { titre: string; montant: string | null } | null;
}

function jours(d: ProjectDeadline): string {
  if (d.joursRestants < 0) return 'Dépassée';
  if (d.joursRestants === 0) return "Aujourd'hui";
  return `J-${d.joursRestants}`;
}

/**
 * Échéancier du projet (maquette : la bande bleue « N dates à ne pas
 * manquer ») : une carte par date limite d'aide ou échéance de dossier, de la
 * plus proche à la plus lointaine, avec son compte à rebours et une jauge qui
 * se remplit à l'approche. La plus proche est cerclée d'orange.
 *
 * Chaque carte mène là où l'échéance se traite — la fiche de l'aide, ou le
 * dossier (cf. `deadlineLink`).
 *
 * L'échéancier lui-même est réservé à l'offre Veille : c'est la page du projet
 * qui le décide (`offre.echeancier`), ce composant n'en sait rien. Il peut donc
 * porter des lignes dont le nom d'aide est masqué — une aide à venir sur un
 * compte gratuit, vue par un membre d'une équipe dont le propriétaire est
 * abonné : le nom est retiré côté serveur, et le lien renvoie de lui-même vers
 * les tarifs.
 */
export function ProjectEcheancier({ deadlines, aide }: ProjectEcheancierProps) {
  const [tout, setTout] = useState(false);
  if (deadlines.length === 0) return null;
  const visibles = tout ? deadlines : deadlines.slice(0, VISIBLES);
  const n = deadlines.length;

  return (
    <section className="ech" aria-labelledby="ech-t" data-guide="projet.echeancier">
      <div className="ech-h">
        <div>
          <span className="eyebrow">Échéancier</span>
          <h2 id="ech-t">
            {n === 1 ? 'Une date à ne pas manquer' : `${n} dates à ne pas manquer`}
          </h2>
        </div>
        <p>Les dates limites de dépôt de vos aides, de la plus proche à la plus lointaine.</p>
      </div>
      <div className="ech-grid">
        {visibles.map((d, i) => {
          const urgent = d.joursRestants <= SEUIL_URGENT;
          const pct = d.joursRestants < 0 ? 100 : Math.max(6, 100 - (d.joursRestants / HORIZON) * 100);
          const redige = d.source === 'aide' && d.aideId ? aide?.(d.aideId) : null;
          const sous =
            d.source === 'dossier' ? 'Échéance de dossier' : redige?.montant ?? 'Montant non publié';
          return (
            <Link key={d.id} to={deadlineLink(d)} className={i === 0 ? 'dl urgent' : 'dl'}>
              <div className="dl-top">
                <span className="dl-date">
                  {format(parseISO(d.date), 'd MMM', { locale: fr })}
                  <small>{sous}</small>
                </span>
                <span className={`jx ${d.joursRestants < 0 ? 'passe' : urgent ? 'urg' : 'calm'}`}>{jours(d)}</span>
              </div>
              <div className={urgent ? 'bar' : 'bar calm'} aria-hidden="true">
                <i style={{ width: `${pct}%` }} />
              </div>
              <p>{redige?.titre ?? d.label}</p>
              <span className="dl-f">
                {d.source === 'aide' ? "Voir l'aide" : 'Voir le dossier'}
                <Picto nom="fleche" />
              </span>
            </Link>
          );
        })}
      </div>
      {n > VISIBLES && (
        <button className="ech-all" type="button" onClick={() => setTout((t) => !t)}>
          {tout ? 'Ne montrer que les plus proches' : `Voir les ${n - VISIBLES} autres dates`}
        </button>
      )}
    </section>
  );
}

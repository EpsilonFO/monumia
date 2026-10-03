import { Link } from 'react-router';
import { IconLocalisation, IconEcheance, IconDossier, IconProjet } from '@/components/icons';
import { Clover } from '@/components/illustrations';
import { MemberAvatarStack } from '@/components/sharing/MemberAvatarStack';
import { ROUTES } from '@/constants/routes';
import { C, DEADLINE_TONE, SERIF } from '@/lib/brand';
import { deadlineLabel } from '@/lib/date-utils';
import { monumentPhotoUrl } from '@/lib/monument-photo';
import { isProjectShared } from '@/lib/project-permissions';
import type { MonumentStats } from '@/lib/project-stats';
import type { Monument } from '@/types';

interface MonumentCardProps {
  monument: Monument;
  stats?: MonumentStats;
}

/**
 * La photo du monument, en grand : les trois quarts de la carte. Elle est
 * recadrée une seule fois en 16:9 (cf. MonumentPhotoProfil) et sert telle
 * quelle du tableau de bord à cette liste. Sans photo, la fleur Monumia en
 * blanc sur bleu profond ancre la marque plutôt qu'un cadre vide.
 */
function Photo({ photo }: { photo: string | null }) {
  return (
    <div
      className="relative h-52 overflow-hidden sm:h-full sm:min-h-[17rem]"
      style={photo ? undefined : { background: `linear-gradient(135deg, ${C.blue}, ${C.blueDark})` }}
      aria-hidden
    >
      {photo ? (
        <div
          className="absolute inset-0 bg-cover bg-center transition-transform duration-700 ease-out group-hover:scale-[1.05]"
          style={{ backgroundImage: `url(${photo})` }}
        />
      ) : (
        <Clover
          size={260}
          className="pointer-events-none absolute -right-12 -top-16 text-white"
          style={{ opacity: 0.1 }}
        />
      )}
    </div>
  );
}

/**
 * Carte d'un monument dans « Mes monuments ». Elle répond à deux questions,
 * dans cet ordre : quel bien, et que faire maintenant. Le détail par chantier
 * est un cran plus bas, sur la page du monument, onglet « Projets ».
 *
 * La photo tient les trois quarts de la largeur et le texte la colonne de
 * droite : sur une liste de biens, on reconnaît le sien à l'image bien avant de
 * lire son nom. Pas de bouton d'action — la carte entière est le lien, une
 * flèche en plus ne ferait que répéter ce que le survol dit déjà.
 */
export function MonumentCard({ monument, stats }: MonumentCardProps) {
  const shared = isProjectShared(monument);
  const members = monument.members ?? [];
  const photo = monumentPhotoUrl(monument);

  const nbProjets = stats?.projets ?? 0;
  const dossiersActifs = stats?.dossiersActifs ?? 0;

  // Échéance affichée UNIQUEMENT si elle presse (dépassée, urgente, ou proche).
  const next = stats?.prochaineEcheance ?? null;
  const nextLabel = next ? deadlineLabel(next.date) : null;
  const pressing = nextLabel && nextLabel.urgency !== 'normal';
  const tone = nextLabel ? DEADLINE_TONE[nextLabel.urgency] : null;

  return (
    <Link to={ROUTES.MONUMENT_DETAIL(monument.id)} className="group block">
      <article
        className="grid overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_24px_50px_-28px_rgba(7,42,114,0.55)] sm:grid-cols-[3fr_1fr]"
        style={{ background: C.card, borderColor: C.border }}
      >
        <Photo photo={photo} />

        {/* ── Colonne de droite : le nom, puis les faits qui pressent. ── */}
        <div className="flex min-w-0 flex-col justify-center gap-3 p-5 sm:p-6">
          <div className="min-w-0">
            <h3
              className="line-clamp-3 text-[24px] font-bold leading-snug"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {monument.nom}
            </h3>
            {(monument.commune || monument.departement) && (
              <p className="mt-1 flex items-center gap-1.5 text-[15.5px]" style={{ color: C.grayFg }}>
                <IconLocalisation className="h-4 w-4 shrink-0" strokeWidth={1.8} aria-hidden />
                <span className="truncate">
                  {monument.commune ?? '—'}
                  {monument.departement ? ` · ${monument.departement}` : ''}
                </span>
              </p>
            )}
          </div>

          <div className="flex min-w-0 flex-col gap-2">
            <span
              className="inline-flex items-center gap-1.5 text-[15px] font-medium"
              style={{ color: C.grayFg }}
            >
              <IconProjet className="h-4 w-4 shrink-0" aria-hidden />
              {nbProjets === 0
                ? 'Aucun projet'
                : `${nbProjets} projet${nbProjets > 1 ? 's' : ''} de travaux`}
            </span>
            {dossiersActifs > 0 && (
              <span
                className="inline-flex items-center gap-1.5 text-[15px] font-medium"
                style={{ color: C.grayFg }}
              >
                <IconDossier className="h-4 w-4 shrink-0" aria-hidden />
                {dossiersActifs} dossier{dossiersActifs > 1 ? 's' : ''} en cours
              </span>
            )}
            {pressing && nextLabel && tone && (
              <span
                className="inline-flex w-fit items-center gap-1.5 rounded-full px-3 py-1.5 text-[15px] font-semibold"
                style={{ color: tone.fg, background: tone.tint }}
              >
                <IconEcheance className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden />
                {nextLabel.urgency === 'past'
                  ? 'Échéance dépassée'
                  : `Échéance : ${nextLabel.text.toLowerCase()}`}
              </span>
            )}
          </div>

          {shared && members.length > 0 && <MemberAvatarStack people={members} size="sm" />}
        </div>
      </article>
    </Link>
  );
}

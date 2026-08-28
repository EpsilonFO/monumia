import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { IconLocalisation, IconEcheance, IconDossier } from '@/components/icons';
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
 * Vignette du monument : photo 16:9 arrondie — le format du héros du tableau de
 * bord, pour qu'une photo recadrée une fois serve partout sans être retaillée.
 * Sans photo, la fleur Monumia en blanc sur bleu profond ancre la marque.
 */
function PhotoThumb({ photo }: { photo: string | null }) {
  return (
    <div
      className="flex aspect-video w-28 shrink-0 items-center justify-center overflow-hidden rounded-xl"
      style={{
        background: photo ? undefined : `linear-gradient(150deg, ${C.blue}, ${C.blueDark})`,
        boxShadow: 'inset 0 0 0 1px rgba(7,42,114,0.08)',
      }}
      aria-hidden
    >
      {photo ? (
        <div
          className="h-full w-full bg-cover bg-center transition-transform duration-500 ease-out group-hover:scale-[1.06]"
          style={{ backgroundImage: `url(${photo})` }}
        />
      ) : (
        <Clover size={28} className="text-white" style={{ opacity: 0.9 }} />
      )}
    </div>
  );
}

/**
 * Carte d'un monument dans « Mes monuments ». Elle répond à deux questions,
 * dans cet ordre : quel bien, et que faire maintenant. Le détail par chantier
 * est un cran plus bas, sur la page du monument, onglet « Projets ».
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

  // Le bouton dit la prochaine chose à faire, jamais un « Voir » ambigu.
  const cta = nbProjets === 0 ? 'Lancer un projet de travaux' : 'Ouvrir le monument';

  return (
    <Link to={ROUTES.MONUMENT_DETAIL(monument.id)} className="block">
      <article
        className="group overflow-hidden rounded-2xl border p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_20px_45px_-24px_rgba(7,42,114,0.45)] sm:p-6"
        style={{ background: C.card, borderColor: C.border }}
      >
        {/* ── En-tête : vignette + nom + lieu, avatars si partagé, et le bouton
            d'action aligné sur le titre. Sur mobile, il passe à la ligne. ── */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <PhotoThumb photo={photo} />
          <div className="min-w-0 flex-1 basis-[11rem]">
            <h3
              className="line-clamp-2 text-[20px] font-bold leading-snug"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {monument.nom}
            </h3>
            {(monument.commune || monument.departement) && (
              <p
                className="mt-0.5 flex items-center gap-1.5 text-[13.5px]"
                style={{ color: C.grayFg }}
              >
                <IconLocalisation className="h-4 w-4 shrink-0" strokeWidth={1.8} aria-hidden />
                <span className="truncate">
                  {monument.commune ?? '—'}
                  {monument.departement ? ` · ${monument.departement}` : ''}
                </span>
              </p>
            )}
          </div>
          {shared && members.length > 0 && (
            <div className="shrink-0">
              <MemberAvatarStack people={members} size="sm" />
            </div>
          )}
          <span
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-[14px] font-semibold text-white transition-all group-hover:shadow-md max-sm:w-full"
            style={{ background: C.orange }}
          >
            {cta}
            <ArrowRight
              className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5"
              aria-hidden
            />
          </span>
        </div>

        {/* ── Pied : les faits qui pressent, quand il y en a. ── */}
        {(dossiersActifs > 0 || (pressing && nextLabel && tone)) && (
          <div className="mt-4 flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
            {dossiersActifs > 0 && (
              <span
                className="inline-flex items-center gap-1.5 text-[13px] font-medium"
                style={{ color: C.grayFg }}
              >
                <IconDossier className="h-4 w-4 shrink-0" aria-hidden />
                {dossiersActifs} dossier{dossiersActifs > 1 ? 's' : ''} en cours
              </span>
            )}
            {pressing && nextLabel && tone && (
              <span
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold"
                style={{ color: tone.fg, background: tone.tint }}
              >
                <IconEcheance className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden />
                {nextLabel.urgency === 'past'
                  ? 'Échéance dépassée'
                  : `Échéance : ${nextLabel.text.toLowerCase()}`}
              </span>
            )}
          </div>
        )}
      </article>
    </Link>
  );
}

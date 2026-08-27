import { Skeleton } from '@/components/ui/skeleton';
import { C } from '@/lib/brand';

/**
 * Squelettes du tableau de bord : carte agenda et grille de projets
 * reprennent exactement les gabarits de leurs homologues réels.
 */

/** Carte agenda unifiée (miroir de NextActionCard : éphéméride + action + CTA). */
export function NextActionCardSkeleton() {
  return (
    <div
      className="overflow-hidden rounded-2xl border"
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      <div className="flex flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center">
        <Skeleton className="h-16 w-14 shrink-0 rounded-2xl" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-3 w-44" />
          <Skeleton className="h-5 w-3/5 max-w-[360px]" />
          <Skeleton className="h-3.5 w-36" />
        </div>
        <Skeleton className="h-10 w-40 shrink-0 self-start rounded-xl sm:self-center" />
      </div>
    </div>
  );
}

/** Carte projet héros : photo en haut, parcours et métadonnées dans le corps crème. */
function ProjectHeroCardSkeleton({ featured = false }: { featured?: boolean }) {
  return (
    <div
      className="flex h-full flex-col overflow-hidden rounded-2xl border"
      style={{ background: C.card, borderColor: C.border }}
    >
      <Skeleton className={`w-full rounded-none ${featured ? 'h-60 sm:h-72' : 'h-48'}`} />
      <div className={`flex flex-1 flex-col gap-3 ${featured ? 'px-6 py-5 md:px-7' : 'px-5 py-4'}`}>
        <div className="border-b pb-3" style={{ borderColor: C.border }}>
          <Skeleton className="h-5 w-4/5" />
        </div>
        <div className="flex items-center justify-between gap-4">
          <Skeleton className="h-3.5 w-32" />
          <Skeleton className="h-3.5 w-24" />
        </div>
      </div>
    </div>
  );
}

/** Grille « Vos projets » (miroir de ProjectsInProgress : 1 héros ou grille 2-3). */
export function ProjectsInProgressSkeleton({ count = 2 }: { count?: number }) {
  if (count <= 1) return <ProjectHeroCardSkeleton featured />;
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 2xl:grid-cols-3">
      {Array.from({ length: Math.min(count, 3) }, (_, i) => (
        <ProjectHeroCardSkeleton key={i} />
      ))}
    </div>
  );
}

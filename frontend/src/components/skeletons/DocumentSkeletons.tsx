import { Skeleton } from '@/components/ui/skeleton';
import { C } from '@/lib/brand';

/**
 * Squelettes de l'écran « Documents » : rangées au même gabarit que DocumentTile.
 */

/** Rangée document pleine largeur (miroir de DocumentTile : icône, titre, pied d'actions). */
function DocumentRowSkeleton() {
  return (
    <div
      className="flex flex-col overflow-hidden rounded-2xl border"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="flex flex-1 flex-col px-5 pb-3 pt-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <Skeleton className="h-10 w-10 shrink-0 rounded-lg" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-32" />
            </div>
          </div>
          <Skeleton className="h-5 w-16 rounded-md" />
        </div>
      </div>
      <div
        className="flex items-center justify-between gap-2 border-t px-5 py-3"
        style={{ borderColor: C.border }}
      >
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-[34px] w-28 rounded-lg" />
      </div>
    </div>
  );
}

/** Page « Mes documents » : sections par projet (en-tête + rangées empilées). */
export function DocumentsListSkeleton() {
  return (
    <div className="space-y-8">
      {[3, 2].map((rows, s) => (
        <section key={s} className="space-y-3">
          <div
            className="flex items-center gap-2.5 border-b pb-2"
            style={{ borderColor: C.border }}
          >
            <Skeleton className="h-3 w-3 rounded-full" />
            <Skeleton className="h-4 w-44" />
          </div>
          <div className="flex flex-col gap-3">
            {Array.from({ length: rows }, (_, i) => (
              <DocumentRowSkeleton key={i} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

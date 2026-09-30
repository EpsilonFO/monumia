import { Skeleton } from '@/components/ui/skeleton';
import { C } from '@/lib/brand';

/**
 * Squelettes des écrans « Projets » : mêmes gabarits (cartes, tuiles, onglets)
 * que les vrais composants, en voiles crème animés — l'utilisateur voit la
 * page se dessiner avant que les données n'arrivent.
 */

/** Carte projet de la liste (miroir de ProjectCard : en-tête, deux tuiles, pied). */
export function ProjectCardSkeleton() {
  return (
    <div
      className="overflow-hidden rounded-2xl border p-5 sm:p-6"
      style={{ background: C.card, borderColor: C.border }}
    >
      {/* En-tête : vignette + nom + lieu */}
      <div className="flex items-center gap-4">
        <Skeleton className="h-16 w-16 shrink-0 rounded-xl" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-5 w-2/5 max-w-[319px]" />
          <Skeleton className="h-3.5 w-1/4 max-w-[193.5px]" />
        </div>
      </div>

      {/* Tuiles aides + avancement */}
      <div className="mt-4 flex flex-col gap-3 lg:flex-row">
        <Skeleton className="h-[118.5px] rounded-xl lg:w-64 lg:shrink-0" />
        <Skeleton className="h-[118.5px] flex-1 rounded-xl" />
      </div>

      {/* Pied : faits + bouton d'action */}
      <div className="mt-4 flex items-center justify-between gap-3">
        <Skeleton className="h-4 w-36" />
        <Skeleton className="h-10 w-44 rounded-lg" />
      </div>
    </div>
  );
}

/** Liste verticale de la page « Mes projets ». */
export function ProjectListSkeleton({ count = 2 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }, (_, i) => (
        <ProjectCardSkeleton key={i} />
      ))}
    </div>
  );
}

/** Page détail projet : fil d'Ariane, barre résumé, onglets, contenu. */
export function ProjectDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-52" />

      {/* Barre résumé (vignette + titre + stats) */}
      <div
        className="flex items-center gap-4 rounded-2xl border px-5 py-4"
        style={{ background: C.card, borderColor: C.border }}
      >
        <Skeleton className="h-16 w-16 shrink-0 rounded-xl" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-5 w-1/3 max-w-[341.5px]" />
          <Skeleton className="h-3.5 w-1/4 max-w-[205px]" />
        </div>
        <Skeleton className="hidden h-10 w-40 rounded-lg sm:block" />
      </div>

      {/* Onglets */}
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-[59px] rounded-xl" />
        ))}
      </div>

      {/* Contenu de l'onglet (grille de cartes) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-44 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}

/** Page détail dossier : fil d'Ariane, titre, statut, checklist des pièces. */
export function DossierDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-64" />
      <Skeleton className="h-8 w-2/3 max-w-[546.5px]" />
      <Skeleton className="h-10 w-56 rounded-lg" />

      {/* Bloc « Pièces du dossier » */}
      <div
        className="overflow-hidden rounded-2xl border"
        style={{ background: C.card, borderColor: C.border }}
      >
        <div className="border-b px-5 py-3" style={{ borderColor: C.border }}>
          <Skeleton className="h-5 w-40" />
        </div>
        <div className="space-y-3 px-5 py-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="h-5 w-5 shrink-0 rounded-md" />
              <Skeleton className="h-4 flex-1 max-w-[478px]" />
              <Skeleton className="h-8 w-28 shrink-0 rounded-lg" />
            </div>
          ))}
        </div>
      </div>

      {/* Section « À propos de l'aide » */}
      <div className="space-y-3 pt-2">
        <Skeleton className="h-5 w-44" />
        <Skeleton className="h-36 rounded-2xl" />
      </div>
    </div>
  );
}

/**
 * Onglet « Aides » d'un projet, le temps que le diagnostic revienne.
 *
 * Le moteur est rapide, mais il reste un aller-retour réseau : sans ce
 * squelette, la page affichait pendant ce temps l'invitation à « lancer le
 * moteur », c'est-à-dire un écran vide alors que le calcul était déjà en
 * cours. On dessine donc le gabarit réel — échéancier, barres de filtre,
 * sections et cartes — plutôt que d'annoncer un travail à faire.
 */
export function AidesTabSkeleton() {
  return (
    <div className="space-y-8">
      {/* Échéancier */}
      <Skeleton className="h-[100.5px] rounded-2xl" />

      {/* Pastilles de financeur, puis puces de famille */}
      <div className="flex flex-wrap gap-2">
        {[120, 96, 140, 104].map((w) => (
          <Skeleton key={w} className="h-[43px] rounded-full" style={{ width: w }} />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {[72, 88, 64, 80, 68].map((w) => (
          <Skeleton key={w} className="h-[30px] rounded-full" style={{ width: w }} />
        ))}
      </div>

      {/* Deux sections de cartes (titre + grille) */}
      {[2, 3].map((cartes) => (
        <div key={cartes} className="space-y-3">
          <Skeleton className="h-5 w-56" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
            {Array.from({ length: cartes }, (_, i) => (
              <Skeleton
                key={i}
                className={`h-[296px] rounded-2xl ${cartes === 2 ? 'lg:col-span-3' : 'lg:col-span-2'}`}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

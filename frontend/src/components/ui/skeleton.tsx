import { cn } from '@/lib/utils';

/**
 * Bloc squelette de base : voile crème animé d'un reflet chaud (`.skeleton-shimmer`,
 * défini dans index.css sur les tokens du thème). Donner la forme via className
 * (h-*, w-*, rounded-*) pour mimer l'élément qu'il remplace.
 */
function Skeleton({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden
      className={cn('skeleton-shimmer rounded-lg', className)}
      {...props}
    />
  );
}

export { Skeleton };
